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
