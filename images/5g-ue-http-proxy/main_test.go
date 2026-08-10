package main

import (
	"net/http"
	"testing"
)

func TestRemoveHopHeaders(t *testing.T) {
	header := http.Header{
		"Connection":       []string{"close"},
		"Proxy-Connection": []string{"keep-alive"},
		"X-Lab":            []string{"5g"},
	}
	removeHopHeaders(header)
	if header.Get("Connection") != "" || header.Get("Proxy-Connection") != "" {
		t.Fatal("hop-by-hop headers were not removed")
	}
	if header.Get("X-Lab") != "5g" {
		t.Fatal("end-to-end header was removed")
	}
}

func TestUploadsUseDedicatedConnections(t *testing.T) {
	p := newProxy("lo", "127.0.0.1:53")

	shared, dedicated := p.requestTransport(http.MethodGet)
	if dedicated || shared != p.transport {
		t.Fatal("GET should use the shared transport")
	}

	upload, dedicated := p.requestTransport(http.MethodPost)
	if !dedicated || upload == p.transport {
		t.Fatal("POST should use a dedicated transport")
	}
	if !upload.DisableKeepAlives {
		t.Fatal("POST transport must disable connection reuse")
	}
}
