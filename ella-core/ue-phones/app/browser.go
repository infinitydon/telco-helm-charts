package gnb

import (
	"context"
	"encoding/binary"
	"encoding/json"
	"fmt"
	"golang.org/x/net/websocket"
	"io"
	"net"
	"net/http"
	"net/http/httputil"
	"net/url"
	"os"
	"os/exec"
	"strconv"
	"time"
)

// Browser UID 1000 may use loopback only. DNS and TCP egress are handled
// here with sockets bound to this phone's internet PDU address.
func (d *phoneDashboard) startBrowserProxy() error {
	if len(d.phones) != 1 {
		return fmt.Errorf("remote browser requires one UE per deployment")
	}
	for _, firewall := range []string{"iptables", "ip6tables"} {
		for _, args := range [][]string{
			{"-N", "ELLA_BROWSER"}, {"-F", "ELLA_BROWSER"},
			{"-A", "ELLA_BROWSER", "-o", "lo", "-j", "RETURN"},
			{"-A", "ELLA_BROWSER", "-m", "conntrack", "--ctstate", "ESTABLISHED,RELATED", "-j", "RETURN"},
			{"-A", "ELLA_BROWSER", "-j", "REJECT"},
		} {
			if out, err := exec.Command(firewall, args...).CombinedOutput(); err != nil && args[0] != "-N" {
				return fmt.Errorf("browser firewall: %s: %w", out, err)
			}
		}
		if exec.Command(firewall, "-C", "OUTPUT", "-m", "owner", "--uid-owner", "1000", "-j", "ELLA_BROWSER").Run() != nil {
			if out, err := exec.Command(firewall, "-I", "OUTPUT", "1", "-m", "owner", "--uid-owner", "1000", "-j", "ELLA_BROWSER").CombinedOutput(); err != nil {
				return fmt.Errorf("browser firewall: %s: %w", out, err)
			}
		}
	}
	listener, err := net.Listen("tcp", "127.0.0.1:1080")
	if err != nil {
		return err
	}
	p := d.phones[0]
	go func() {
		for {
			conn, err := listener.Accept()
			if err != nil {
				return
			}
			go d.socks(conn, p)
		}
	}()
	return nil
}
func (d *phoneDashboard) socks(c net.Conn, p *dashboardPhone) {
	defer c.Close()
	c.SetDeadline(time.Now().Add(15 * time.Second))
	var greeting [2]byte
	if _, e := io.ReadFull(c, greeting[:]); e != nil || greeting[0] != 5 {
		return
	}
	methods := make([]byte, int(greeting[1]))
	if _, e := io.ReadFull(c, methods); e != nil {
		return
	}
	noAuth := false
	for _, m := range methods {
		if m == 0 {
			noAuth = true
		}
	}
	if !noAuth {
		c.Write([]byte{5, 255})
		return
	}
	c.Write([]byte{5, 0})
	var header [4]byte
	if _, e := io.ReadFull(c, header[:]); e != nil || header[0] != 5 || header[1] != 1 {
		return
	}
	host := ""
	switch header[3] {
	case 1:
		b := make([]byte, 4)
		if _, e := io.ReadFull(c, b); e != nil {
			return
		}
		host = net.IP(b).String()
	case 3:
		var n [1]byte
		if _, e := io.ReadFull(c, n[:]); e != nil {
			return
		}
		b := make([]byte, int(n[0]))
		if _, e := io.ReadFull(c, b); e != nil {
			return
		}
		host = string(b)
	default:
		return
	}
	var portBytes [2]byte
	if _, e := io.ReadFull(c, portBytes[:]); e != nil {
		return
	}
	port := binary.BigEndian.Uint16(portBytes[:])
	if port != 80 && port != 443 {
		c.Write([]byte{5, 2, 0, 1, 0, 0, 0, 0, 0, 0})
		return
	}
	client := ueWebClient(p.internetIP)
	transport := client.Transport.(*http.Transport)
	defer transport.CloseIdleConnections()
	ctx, cancel := context.WithTimeout(context.Background(), 12*time.Second)
	defer cancel()
	upstream, err := transport.DialContext(ctx, "tcp", net.JoinHostPort(host, strconv.Itoa(int(port))))
	if err != nil {
		c.Write([]byte{5, 4, 0, 1, 0, 0, 0, 0, 0, 0})
		return
	}
	defer upstream.Close()
	c.Write([]byte{5, 0, 0, 1, 0, 0, 0, 0, 0, 0})
	c.SetDeadline(time.Time{})
	upstream.SetDeadline(time.Now().Add(5 * time.Minute))
	d.event(p.id, "Chromium via UE "+p.internetIP+": "+host)
	done := make(chan struct{})
	go func() {
		io.Copy(upstream, c)
		if t, ok := upstream.(*net.TCPConn); ok {
			t.CloseWrite()
		}
		close(done)
	}()
	io.Copy(c, upstream)
	c.Close()
	upstream.Close()
	<-done
}
func (d *phoneDashboard) browserRoutes(mux *http.ServeMux) {
	mux.HandleFunc("GET /api/browser", func(w http.ResponseWriter, r *http.Request) {
		w.Header().Set("Content-Type", "application/json")
		json.NewEncoder(w).Encode(map[string]any{"enabled": os.Getenv("BROWSER_ENABLED") == "true"})
	})
	target, _ := url.Parse("http://127.0.0.1:6080")
	proxy := httputil.NewSingleHostReverseProxy(target)
	mux.Handle("GET /browser/", http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		if origin := r.Header.Get("Origin"); origin != "" {
			u, e := url.Parse(origin)
			if e != nil || u.Host != r.Host {
				http.Error(w, "same-origin requests only", 403)
				return
			}
		}
		http.StripPrefix("/browser", proxy).ServeHTTP(w, r)
	}))
	mux.HandleFunc("POST /api/browser/navigate", func(w http.ResponseWriter, r *http.Request) {
		if os.Getenv("BROWSER_ENABLED") != "true" {
			http.Error(w, "browser disabled", 409)
			return
		}
		if origin := r.Header.Get("Origin"); origin != "" {
			u, e := url.Parse(origin)
			if e != nil || u.Host != r.Host {
				http.Error(w, "same-origin requests only", 403)
				return
			}
		}
		var req struct {
			URL string `json:"url"`
		}
		if json.NewDecoder(http.MaxBytesReader(w, r.Body, 4096)).Decode(&req) != nil {
			http.Error(w, "invalid request", 400)
			return
		}
		u, err := publicWebURL(req.URL)
		if err != nil {
			http.Error(w, err.Error(), 400)
			return
		}
		client := &http.Client{Timeout: 5 * time.Second}
		response, err := client.Get("http://127.0.0.1:9222/json/list")
		if err != nil {
			http.Error(w, "Chromium is starting; try again", 503)
			return
		}
		var tabs []struct {
			Type                 string
			WebSocketDebuggerURL string
		}
		json.NewDecoder(response.Body).Decode(&tabs)
		response.Body.Close()
		for _, tab := range tabs {
			if tab.Type != "page" {
				continue
			}
			ws, err := websocket.Dial(tab.WebSocketDebuggerURL, "", "http://localhost")
			if err != nil {
				http.Error(w, err.Error(), 502)
				return
			}
			defer ws.Close()
			ws.SetDeadline(time.Now().Add(10 * time.Second))
			commands := []map[string]any{
				{"id": 1, "method": "Emulation.setDeviceMetricsOverride", "params": map[string]any{"width": 500, "height": 900, "deviceScaleFactor": 1, "mobile": true}},
				{"id": 2, "method": "Emulation.setTouchEmulationEnabled", "params": map[string]any{"enabled": true}},
				{"id": 3, "method": "Network.setUserAgentOverride", "params": map[string]any{"userAgent": "Mozilla/5.0 (Linux; Android 14; Mobile) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/130.0.0.0 Mobile Safari/537.36"}},
				{"id": 4, "method": "Page.navigate", "params": map[string]any{"url": u.String()}},
			}
			for _, command := range commands {
				if err := websocket.JSON.Send(ws, command); err != nil {
					http.Error(w, err.Error(), 502)
					return
				}
				for {
					var message map[string]any
					if err := websocket.JSON.Receive(ws, &message); err != nil {
						http.Error(w, err.Error(), 502)
						return
					}
					if message["id"] == float64(command["id"].(int)) {
						if message["error"] != nil {
							http.Error(w, fmt.Sprint(message["error"]), 502)
							return
						}
						break
					}
				}
			}
			w.Header().Set("Content-Type", "application/json")
			io.WriteString(w, `{"ok":true}`)
			return
		}
		http.Error(w, "Chromium page is not ready", 503)
	})
}
