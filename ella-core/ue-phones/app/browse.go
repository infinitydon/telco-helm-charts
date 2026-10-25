package gnb

import (
	"context"
	"encoding/json"
	"fmt"
	"io"
	"net"
	"net/http"
	"net/netip"
	"net/url"
	"strings"
	"time"

	radio "github.com/ellanetworks/core/internal/tester/gnb"
	"github.com/vishvananda/netlink"
	"golang.org/x/net/html"
)

type internetSessionInfo = radio.PDUSessionResult

func attachInternet(p *dashboardPhone, index int) error {
	session, err := p.access.leg.gnb.DashboardInternetSession(p.access.ue, p.access.leg.ranUEID)
	if err != nil {
		return err
	}
	name := fmt.Sprintf("ellaweb%d", index)
	if err = p.access.leg.gnb.AddTunnel(&radio.TunnelOpts{UEIPv4: session.UEIPv4 + "/32", UpfAddress: session.UpfAddress, ULTEID: session.ULTEID, DLTEID: session.DLTEID, QFI: session.QFI, TunInterfaceName: name}); err != nil {
		return err
	}
	link, err := netlink.LinkByName(name)
	if err != nil {
		return err
	}
	table := 200 + index
	_, all, _ := net.ParseCIDR("0.0.0.0/0")
	if err = netlink.RouteReplace(&netlink.Route{LinkIndex: link.Attrs().Index, Dst: all, Table: table, Scope: netlink.SCOPE_UNIVERSE}); err != nil {
		return err
	}
	rule := netlink.NewRule()
	rule.Table = table
	rule.Priority = 1200 + index
	rule.Src = &net.IPNet{IP: net.ParseIP(session.UEIPv4), Mask: net.CIDRMask(32, 32)}
	if err = netlink.RuleAdd(rule); err != nil {
		return err
	}
	p.internetIP = session.UEIPv4
	p.internetSession = session
	p.access.leg.gnb.WatchTEID(session.DLTEID)
	return nil
}

func publicWebURL(raw string) (*url.URL, error) {
	if len(raw) > 2048 {
		return nil, fmt.Errorf("URL is too long")
	}
	u, err := url.Parse(raw)
	if err != nil || u.Hostname() == "" || u.User != nil || (u.Scheme != "http" && u.Scheme != "https") {
		return nil, fmt.Errorf("enter a public http:// or https:// URL without credentials")
	}
	if port := u.Port(); port != "" && port != "80" && port != "443" {
		return nil, fmt.Errorf("only public HTTP/HTTPS ports are supported")
	}
	return u, nil
}
func publicIP(addr netip.Addr) bool {
	addr = addr.Unmap()
	if !addr.IsGlobalUnicast() || addr.IsPrivate() || addr.IsLoopback() || addr.IsLinkLocalUnicast() {
		return false
	}
	for _, prefix := range []string{"0.0.0.0/8", "100.64.0.0/10", "192.0.0.0/24", "198.18.0.0/15", "240.0.0.0/4"} {
		if netip.MustParsePrefix(prefix).Contains(addr) {
			return false
		}
	}
	return true
}
func ueWebClient(source string) *http.Client {
	local := net.ParseIP(source)
	resolver := &net.Resolver{PreferGo: true, Dial: func(ctx context.Context, network, address string) (net.Conn, error) {
		var bind net.Addr = &net.UDPAddr{IP: local}
		if strings.HasPrefix(network, "tcp") {
			bind = &net.TCPAddr{IP: local}
		}
		dialer := net.Dialer{LocalAddr: bind, Timeout: 5 * time.Second}
		return dialer.DialContext(ctx, network, "8.8.8.8:53")
	}}
	transport := &http.Transport{Proxy: nil, DisableKeepAlives: true, ResponseHeaderTimeout: 15 * time.Second, TLSHandshakeTimeout: 10 * time.Second, DialContext: func(ctx context.Context, network, address string) (net.Conn, error) {
		host, port, err := net.SplitHostPort(address)
		if err != nil {
			return nil, err
		}
		ips, err := resolver.LookupNetIP(ctx, "ip4", host)
		if err != nil {
			return nil, fmt.Errorf("UE DNS: %w", err)
		}
		if len(ips) == 0 {
			return nil, fmt.Errorf("no IPv4 address found")
		}
		for _, ip := range ips {
			if !publicIP(ip) {
				return nil, fmt.Errorf("private and special-use destinations are not supported")
			}
		}
		var last error
		for _, ip := range ips {
			dialer := net.Dialer{LocalAddr: &net.TCPAddr{IP: local}, Timeout: 8 * time.Second}
			conn, e := dialer.DialContext(ctx, "tcp4", net.JoinHostPort(ip.String(), port))
			if e == nil {
				return conn, nil
			}
			last = e
		}
		return nil, last
	}}
	return &http.Client{Transport: transport, Timeout: 25 * time.Second, CheckRedirect: func(r *http.Request, via []*http.Request) error {
		if len(via) >= 5 {
			return fmt.Errorf("too many redirects")
		}
		_, err := publicWebURL(r.URL.String())
		return err
	}}
}

type webLink struct {
	Text string `json:"text"`
	URL  string `json:"url"`
}

// Keep document structure without allowing remote code, styles, or resource loads.
// Every navigable link is sent back through the selected UE by the dashboard.
func mobileReader(body string, base *url.URL) string {
	root, err := html.Parse(strings.NewReader(body))
	if err != nil {
		return ""
	}
	var out strings.Builder
	var walk func(*html.Node)
	walk = func(n *html.Node) {
		if out.Len() > 128000 {
			return
		}
		if n.Type == html.TextNode {
			out.WriteString(html.EscapeString(n.Data))
			return
		}
		tag := ""
		if n.Type == html.ElementNode {
			switch n.Data {
			case "head", "script", "style", "noscript", "svg", "iframe", "form", "nav", "footer", "template", "object", "embed":
				return
			case "h1", "h2", "h3", "h4", "h5", "h6", "p", "ul", "ol", "li", "blockquote", "pre", "code", "strong", "em", "b", "i", "br", "hr", "table", "thead", "tbody", "tr", "th", "td", "article", "section", "div", "figure", "figcaption":
				tag = n.Data
				out.WriteString("<" + tag + ">")
			case "a":
				for _, a := range n.Attr {
					if a.Key == "href" {
						u, e := url.Parse(a.Val)
						if e == nil {
							u = base.ResolveReference(u)
							if _, e = publicWebURL(u.String()); e == nil {
								tag = "a"
								out.WriteString("<a href=\"#\" data-web-link=\"" + html.EscapeString(u.String()) + "\">")
							}
						}
						break
					}
				}
			}
		}
		for c := n.FirstChild; c != nil; c = c.NextSibling {
			walk(c)
		}
		if tag != "" && tag != "br" && tag != "hr" {
			out.WriteString("</" + tag + ">")
		}
	}
	walk(root)
	return out.String()
}

func reader(body string, base *url.URL) (string, string, []webLink) {
	root, err := html.Parse(strings.NewReader(body))
	if err != nil {
		return "", body, nil
	}
	var text strings.Builder
	title := ""
	links := []webLink{}
	seen := map[string]bool{}
	var contents func(*html.Node) string
	contents = func(n *html.Node) string {
		if n.Type == html.TextNode {
			return n.Data
		}
		var s strings.Builder
		for c := n.FirstChild; c != nil; c = c.NextSibling {
			s.WriteString(contents(c))
			s.WriteByte(' ')
		}
		return strings.Join(strings.Fields(s.String()), " ")
	}
	var walk func(*html.Node)
	walk = func(n *html.Node) {
		if text.Len() > 32000 {
			return
		}
		if n.Type == html.ElementNode {
			switch n.Data {
			case "script", "style", "noscript", "svg", "iframe", "form", "nav", "footer":
				return
			case "title":
				title = contents(n)
				return
			}
			if n.Data == "a" && len(links) < 30 {
				for _, a := range n.Attr {
					if a.Key == "href" {
						u, e := url.Parse(a.Val)
						if e == nil {
							u = base.ResolveReference(u)
							if _, e = publicWebURL(u.String()); e == nil && !seen[u.String()] {
								label := contents(n)
								if label != "" {
									links = append(links, webLink{label, u.String()})
									seen[u.String()] = true
								}
							}
						}
					}
				}
			}
			switch n.Data {
			case "p", "div", "h1", "h2", "h3", "li", "br", "article":
				text.WriteByte('\n')
			}
		}
		if n.Type == html.TextNode {
			clean := strings.Join(strings.Fields(n.Data), " ")
			if clean != "" {
				text.WriteString(clean)
				text.WriteByte(' ')
			}
		}
		for c := n.FirstChild; c != nil; c = c.NextSibling {
			walk(c)
		}
	}
	walk(root)
	lines := []string{}
	for _, line := range strings.Split(text.String(), "\n") {
		line = strings.TrimSpace(line)
		if line != "" {
			lines = append(lines, line)
		}
	}
	return title, strings.Join(lines, "\n\n"), links
}
func (d *phoneDashboard) browse(w http.ResponseWriter, r *http.Request) {
	w.Header().Set("Content-Type", "application/json")
	if origin := r.Header.Get("Origin"); origin != "" {
		u, e := url.Parse(origin)
		if e != nil || u.Host != r.Host {
			http.Error(w, "same-origin requests only", 403)
			return
		}
	}
	var req struct {
		Phone string `json:"phone"`
		URL   string `json:"url"`
	}
	dec := json.NewDecoder(http.MaxBytesReader(w, r.Body, 4096))
	dec.DisallowUnknownFields()
	if err := dec.Decode(&req); err != nil {
		http.Error(w, "invalid request", 400)
		return
	}
	u, err := publicWebURL(req.URL)
	if err != nil {
		w.WriteHeader(400)
		json.NewEncoder(w).Encode(map[string]string{"error": err.Error()})
		return
	}
	d.mu.Lock()
	var p *dashboardPhone
	for _, candidate := range d.phones {
		if candidate.id == req.Phone {
			p = candidate
		}
	}
	ready := d.ready
	d.mu.Unlock()
	if p == nil || !ready || p.internetIP == "" {
		w.WriteHeader(409)
		json.NewEncoder(w).Encode(map[string]string{"error": "UE internet session is not ready"})
		return
	}
	p.webMu.Lock()
	defer p.webMu.Unlock()
	started := time.Now()
	ctx, cancel := context.WithTimeout(r.Context(), 25*time.Second)
	defer cancel()
	request, _ := http.NewRequestWithContext(ctx, http.MethodGet, u.String(), nil)
	request.Header.Set("User-Agent", "Mozilla/5.0 (Linux; Android 14; Mobile) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/130.0.0.0 Mobile Safari/537.36 Ella-UE-Lab/0.2")
	request.Header.Set("Accept", "text/html,text/plain;q=0.9")
	client := ueWebClient(p.internetIP)
	response, err := client.Do(request)
	if err != nil {
		w.WriteHeader(502)
		json.NewEncoder(w).Encode(map[string]string{"error": err.Error()})
		d.event(p.id, "UE browse failed for "+u.Hostname())
		return
	}
	defer response.Body.Close()
	body, err := io.ReadAll(io.LimitReader(response.Body, 1024*1024+1))
	if err != nil || len(body) > 1024*1024 {
		w.WriteHeader(502)
		json.NewEncoder(w).Encode(map[string]string{"error": "page exceeds the 1 MiB reader limit or could not be read"})
		return
	}
	kind := response.Header.Get("Content-Type")
	if !strings.Contains(kind, "text/html") && !strings.Contains(kind, "text/plain") {
		w.WriteHeader(415)
		json.NewEncoder(w).Encode(map[string]string{"error": "reader supports HTML and plain text pages"})
		return
	}
	title, text, links := reader(string(body), response.Request.URL)
	markup := mobileReader(string(body), response.Request.URL)
	if strings.Contains(kind, "text/plain") {
		text = string(body)
		title = response.Request.URL.Hostname()
		markup = "<pre>" + html.EscapeString(text) + "</pre>"
	}
	d.event(p.id, fmt.Sprintf("UE internet: %s returned HTTP %d (%d bytes)", response.Request.URL.Hostname(), response.StatusCode, len(body)))
	json.NewEncoder(w).Encode(map[string]any{"url": response.Request.URL.String(), "title": title, "text": text, "html": markup, "links": links, "status": response.StatusCode, "bytes": len(body), "durationMs": time.Since(started).Milliseconds(), "ueIp": p.internetIP, "uplinkTeid": p.internetSession.ULTEID, "downlinkTeid": p.internetSession.DLTEID})
}
