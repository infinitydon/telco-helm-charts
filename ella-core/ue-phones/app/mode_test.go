package gnb

import (
	"net/http/httptest"
	"strings"
	"testing"
)

func TestPhoneMode(t *testing.T) {
	for _, m := range []string{"", "internet", "internet-ims-sms"} {
		t.Run(m, func(t *testing.T) {
			t.Setenv("UE_MODE", m)
			want := m != "internet"
			if servicesEnabled() != want {
				t.Fatal("incorrect service capability")
			}
		})
	}
}
func TestInternetActionsDisabled(t *testing.T) {
	t.Setenv("UE_MODE", "internet")
	d := &phoneDashboard{ready: true, phones: []*dashboardPhone{{id: "1"}}}
	for _, a := range []string{"register", "unregister", "sms", "call", "answer", "hangup"} {
		r := httptest.NewRequest("POST", "/api/action", strings.NewReader("{\"phone\":\"1\",\"action\":\""+a+"\"}"))
		w := httptest.NewRecorder()
		d.action(w, r)
		if w.Code != 403 {
			t.Fatalf("%s returned %d", a, w.Code)
		}
	}
}
