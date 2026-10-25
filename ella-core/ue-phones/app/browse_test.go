package gnb

import (
	"net/url"
	"strings"
	"testing"
)

func TestMobileReader(t *testing.T) {
	base, _ := url.Parse("https://example.com/news/")
	got := mobileReader(`<html><head><style>body{display:none}</style></head><body onload="bad()"><h1>News</h1><p>Hello <strong>world</strong></p><ul><li>First</li></ul><a href="../next" onclick="bad()">Next</a><a href="javascript:bad()">Bad link</a><img src="https://elsewhere.test/track"><script>bad()</script><iframe src="https://elsewhere.test"></iframe><input autofocus onfocus="bad()"></body></html>`, base)
	for _, want := range []string{`<h1>News</h1>`, `<strong>world</strong>`, `<ul><li>First</li></ul>`, `data-web-link="https://example.com/next"`} {
		if !strings.Contains(got, want) {
			t.Errorf("missing %q in %s", want, got)
		}
	}
	for _, forbidden := range []string{"<script", "<style", "<img", "<iframe", "<input", "onclick", "onload", "javascript:", "elsewhere.test", "bad()"} {
		if strings.Contains(got, forbidden) {
			t.Errorf("unsafe content %q in %s", forbidden, got)
		}
	}
}
