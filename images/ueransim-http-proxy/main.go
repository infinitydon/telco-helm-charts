package main

import (
	"context"
	"errors"
	"fmt"
	"io"
	"log"
	"net"
	"net/http"
	"os"
	"path/filepath"
	"strings"
	"syscall"
	"time"
)

const bindToDevice = 25 // SO_BINDTODEVICE on Linux.

type proxy struct {
	iface     string
	dialer    *net.Dialer
	transport *http.Transport
}

func env(name, fallback string) string {
	if value := strings.TrimSpace(os.Getenv(name)); value != "" {
		return value
	}
	return fallback
}

func waitForInterface(pattern string) string {
	for {
		matches, _ := filepath.Glob(filepath.Join("/sys/class/net", pattern))
		for _, match := range matches {
			name := filepath.Base(match)
			iface, err := net.InterfaceByName(name)
			if err != nil {
				continue
			}
			addresses, err := iface.Addrs()
			if err == nil && len(addresses) > 0 {
				return name
			}
		}
		log.Printf("waiting for interface matching %q", pattern)
		time.Sleep(time.Second)
	}
}

func socketControl(iface string) func(string, string, syscall.RawConn) error {
	return func(_, _ string, raw syscall.RawConn) error {
		var socketErr error
		if err := raw.Control(func(fd uintptr) {
			socketErr = syscall.SetsockoptString(int(fd), syscall.SOL_SOCKET, bindToDevice, iface)
		}); err != nil {
			return err
		}
		return socketErr
	}
}

func newProxy(iface, dnsServer string) *proxy {
	control := socketControl(iface)
	dnsDialer := &net.Dialer{Timeout: 5 * time.Second, Control: control}
	resolver := &net.Resolver{
		PreferGo: true,
		Dial: func(ctx context.Context, _, _ string) (net.Conn, error) {
			return dnsDialer.DialContext(ctx, "udp", dnsServer)
		},
	}
	dialer := &net.Dialer{
		Timeout:   20 * time.Second,
		KeepAlive: 30 * time.Second,
		Resolver:  resolver,
		Control:   control,
	}
	transport := &http.Transport{
		Proxy:                 nil,
		DialContext:           dialer.DialContext,
		ForceAttemptHTTP2:     false,
		MaxIdleConns:          100,
		IdleConnTimeout:       90 * time.Second,
		TLSHandshakeTimeout:   15 * time.Second,
		ExpectContinueTimeout: time.Second,
	}
	return &proxy{iface: iface, dialer: dialer, transport: transport}
}

func removeHopHeaders(header http.Header) {
	for _, name := range []string{
		"Connection", "Proxy-Connection", "Keep-Alive", "Proxy-Authenticate",
		"Proxy-Authorization", "TE", "Trailer", "Transfer-Encoding", "Upgrade",
	} {
		header.Del(name)
	}
}

func copyHeaders(destination, source http.Header) {
	for name, values := range source {
		for _, value := range values {
			destination.Add(name, value)
		}
	}
}

func (p *proxy) ServeHTTP(writer http.ResponseWriter, request *http.Request) {
	if request.Method != http.MethodConnect && request.URL.Path == "/healthz" && request.URL.Host == "" {
		writer.Header().Set("Content-Type", "text/plain")
		writer.WriteHeader(http.StatusOK)
		_, _ = io.WriteString(writer, "ok\n")
		return
	}
	if request.Method == http.MethodConnect {
		p.connect(writer, request)
		return
	}
	p.forward(writer, request)
}

func (p *proxy) connect(writer http.ResponseWriter, request *http.Request) {
	target := request.Host
	if !strings.Contains(target, ":") {
		target += ":443"
	}
	upstream, err := p.dialer.DialContext(request.Context(), "tcp", target)
	if err != nil {
		http.Error(writer, "UE tunnel connection failed", http.StatusBadGateway)
		log.Printf("CONNECT %s via %s failed: %v", target, p.iface, err)
		return
	}
	hijacker, ok := writer.(http.Hijacker)
	if !ok {
		upstream.Close()
		http.Error(writer, "connection hijacking unsupported", http.StatusInternalServerError)
		return
	}
	client, _, err := hijacker.Hijack()
	if err != nil {
		upstream.Close()
		return
	}
	_, _ = client.Write([]byte("HTTP/1.1 200 Connection Established\r\n\r\n"))
	log.Printf("CONNECT %s via %s", target, p.iface)
	go transfer(upstream, client)
	go transfer(client, upstream)
}

func transfer(destination, source net.Conn) {
	_, _ = io.Copy(destination, source)
	_ = destination.Close()
	_ = source.Close()
}

func (p *proxy) forward(writer http.ResponseWriter, request *http.Request) {
	outbound := request.Clone(request.Context())
	outbound.RequestURI = ""
	if outbound.URL.Scheme == "" {
		outbound.URL.Scheme = "http"
	}
	if outbound.URL.Host == "" {
		outbound.URL.Host = request.Host
	}
	removeHopHeaders(outbound.Header)
	response, err := p.transport.RoundTrip(outbound)
	if err != nil {
		http.Error(writer, "UE tunnel request failed", http.StatusBadGateway)
		log.Printf("%s %s via %s failed: %v", request.Method, outbound.URL, p.iface, err)
		return
	}
	defer response.Body.Close()
	removeHopHeaders(response.Header)
	copyHeaders(writer.Header(), response.Header)
	writer.WriteHeader(response.StatusCode)
	_, _ = io.Copy(writer, response.Body)
	log.Printf("%s %s -> %d via %s", request.Method, outbound.URL, response.StatusCode, p.iface)
}

func main() {
	listenAddress := env("LISTEN_ADDRESS", "0.0.0.0:8118")
	interfacePattern := env("UE_INTERFACE_PATTERN", "uesimtun*")
	dnsServer := env("DNS_SERVER", "1.1.1.1:53")
	iface := waitForInterface(interfacePattern)
	handler := newProxy(iface, dnsServer)
	server := &http.Server{
		Addr:              listenAddress,
		Handler:           handler,
		ReadHeaderTimeout: 10 * time.Second,
		IdleTimeout:       90 * time.Second,
	}
	log.Printf("HTTP proxy listening on %s; egress bound to %s; DNS %s", listenAddress, iface, dnsServer)
	if err := server.ListenAndServe(); !errors.Is(err, http.ErrServerClosed) {
		log.Fatal(fmt.Errorf("proxy stopped: %w", err))
	}
}
