package gnb

import (
	"context"
	_ "embed"
	"encoding/binary"
	"encoding/json"
	"fmt"
	"io"
	"log"
	"net/http"
	"net/netip"
	"net/url"
	"os"
	"strings"
	"sync"
	"sync/atomic"
	"time"

	"github.com/ellanetworks/core/internal/tester/scenarios"
	"github.com/ellanetworks/core/nas/sms"
	"github.com/ellanetworks/ims/testue"
)

//go:embed phones.html
var phoneHTML string

//go:embed enhancements.js
var enhancementsJS string

type phoneMessage struct {
	ID        uint64    `json:"id"`
	Direction string    `json:"direction"`
	Peer      string    `json:"peer"`
	Text      string    `json:"text"`
	Status    string    `json:"status"`
	At        time.Time `json:"at"`
}
type phoneEvent struct {
	At    time.Time `json:"at"`
	Phone string    `json:"phone"`
	Text  string    `json:"text"`
}
type dashboardPhone struct {
	mu              sync.Mutex
	op              sync.Mutex
	id, name        string
	endpoint        scenarios.IMSEndpoint
	access          imsCallUE
	ims             *testue.UE
	closeIMS        func()
	call            *testue.Call
	peer            string
	incoming        bool
	messages        []phoneMessage
	tx              atomic.Uint64
	rxBase          int
	rx              int
	errorText       string
	webMu           sync.Mutex
	internetIP      string
	internetSession internetSessionInfo
}
type phoneDashboard struct {
	mu      sync.Mutex
	phones  []*dashboardPhone
	events  []phoneEvent
	ready   bool
	problem string
	next    atomic.Uint64
}

func (d *phoneDashboard) event(id, text string) {
	d.mu.Lock()
	defer d.mu.Unlock()
	d.events = append(d.events, phoneEvent{time.Now().UTC(), id, text})
	if len(d.events) > 100 {
		d.events = d.events[len(d.events)-100:]
	}
	log.Printf("phone=%s %s", id, text)
}
func (d *phoneDashboard) initialize() {
	env := scenarios.Env{CoreN2Addresses: []string{os.Getenv("CORE_N2")}, GNBs: []scenarios.GNB{{Name: "phones", N2Address: os.Getenv("POD_IP"), N3Address: os.Getenv("N3_ADDRESS")}}}
	g, err := startPhoneGNB(env)
	if err != nil {
		d.fail(err)
		return
	}
	subs := []scenarios.SubscriberSpec{
		scenarios.IMSSubscriber("001018400000003", "+15558400003"),
		scenarios.IMSSubscriber("001018400000004", "+15558400004"),
	}
	if os.Getenv("PHONE_ID") == "1" {
		subs = subs[:1]
	} else if os.Getenv("PHONE_ID") == "2" {
		subs = subs[1:]
	}
	var endpoints []scenarios.IMSEndpoint
	var ues []imsCallUE
	if servicesEnabled() {
		endpoints, ues, _, err = attachIMSCallUEs(env, g, subs...)
	} else {
		endpoints, ues, err = attachInternetUEs(env, g, subs...)
	}
	if err != nil {
		g.Close()
		d.fail(err)
		return
	}
	for i, e := range endpoints {
		var u *testue.UE
		var cleanup func()
		if servicesEnabled() {
			u, cleanup, err = scenarios.DashboardIMS(e)
		}
		if err != nil {
			d.fail(err)
			return
		}
		id, name := fmt.Sprint(i+1), fmt.Sprintf("Phone %c", 'A'+i)
		if configured := os.Getenv("PHONE_ID"); configured != "" {
			id = configured
			name = os.Getenv("PHONE_NAME")
		}
		p := &dashboardPhone{id: id, name: name, endpoint: e, access: ues[i], ims: u, closeIMS: cleanup, messages: []phoneMessage{}}
		if err := attachInternet(p, i); err != nil {
			d.fail(fmt.Errorf("internet session for %s: %w", p.name, err))
			return
		}
		p.access.leg.gnb.WatchTEID(p.access.leg.session.DLTEID)
		d.mu.Lock()
		d.phones = append(d.phones, p)
		d.mu.Unlock()
		if servicesEnabled() {
			d.event(p.id, "5G attached; internet and IMS PDU sessions established")
			go d.receiveSMS(p)
			go d.receiveCalls(p)
		} else {
			d.event(p.id, "5G attached; internet-only PDU session established")
		}
	}
	if os.Getenv("BROWSER_ENABLED") == "true" {
		if err := d.startBrowserProxy(); err != nil {
			d.fail(err)
			return
		}
	}
	d.mu.Lock()
	d.ready = true
	d.mu.Unlock()
	if servicesEnabled() {
		d.event("network", "UE ready. Register IMS to make calls; NAS SMS is available immediately.")
	} else {
		d.event("network", "Internet-only UE ready; IMS and SMS disabled.")
	}
}
func (d *phoneDashboard) fail(err error) {
	d.mu.Lock()
	d.problem = err.Error()
	d.mu.Unlock()
	d.event("network", err.Error())
}
func (d *phoneDashboard) receiveSMS(p *dashboardPhone) {
	for {
		m, err := p.access.ue.SMS.Receive(context.Background())
		if err != nil {
			return
		}
		p.mu.Lock()
		p.messages = append(p.messages, phoneMessage{ID: d.next.Add(1), Direction: "received", Peer: m.From, Text: m.Text, Status: "received", At: time.Now().UTC()})
		p.trim()
		p.mu.Unlock()
		d.mu.Lock()
		senders := append([]*dashboardPhone{}, d.phones...)
		d.mu.Unlock()
		for _, sender := range senders {
			if sender.endpoint.Subscriber.MSISDN == m.From {
				sender.mu.Lock()
				for i := range sender.messages {
					sent := &sender.messages[i]
					if sent.Direction == "sent" && sent.Peer == p.endpoint.Subscriber.MSISDN && sent.Text == m.Text && (sent.Status == "submitting" || sent.Status == "accepted by SMSC") {
						sent.Status = "delivered to UE"
						break
					}
				}
				sender.mu.Unlock()
			}
		}
		d.event(p.id, "SMS received from "+m.From)
	}
}
func (p *dashboardPhone) trim() {
	if len(p.messages) > 100 {
		p.messages = p.messages[len(p.messages)-100:]
	}
}
func (d *phoneDashboard) receiveCalls(p *dashboardPhone) {
	for call := range p.ims.MMTel().Calls() {
		p.mu.Lock()
		busy := p.call != nil && p.call.State() != testue.CallTerminated
		if !busy {
			p.call = call
			p.incoming = true
			p.peer = "Incoming call"
			p.tx.Store(0)
			p.rxBase = 0
			p.rx = 0
		}
		p.mu.Unlock()
		if busy {
			_ = call.Reject(486)
			continue
		}
		d.event(p.id, "Incoming IMS call")
		ctx, cancel := context.WithTimeout(context.Background(), 10*time.Second)
		err := call.Ring(ctx)
		cancel()
		if err != nil {
			d.event(p.id, "Ringing: "+err.Error())
		}
		go d.media(p, call)
	}
}

// media sends synthetic RTP through the dedicated voice QFI, never browser audio.
func (d *phoneDashboard) media(p *dashboardPhone, c *testue.Call) {
	tick := time.NewTicker(20 * time.Millisecond)
	defer tick.Stop()
	var seq uint16
	var stamp uint32
	var lastQFI uint8
	for {
		select {
		case <-c.Done():
			d.event(p.id, "Call ended: "+c.End().String())
			return
		case <-tick.C:
		}
		if c.State() != testue.CallConfirmed {
			continue
		}
		stream, ok := c.Stream("audio")
		if !ok || !stream.Remote.Addr.IsValid() {
			continue
		}
		flows := p.access.leg.flows()
		if len(flows) == 0 {
			continue
		}
		qfi := flows[0]
		if lastQFI != qfi {
			p.mu.Lock()
			p.rxBase = p.access.leg.gnb.DownlinkQFICount(p.access.leg.session.DLTEID, qfi)
			p.mu.Unlock()
			lastQFI = qfi
			d.event(p.id, fmt.Sprintf("Voice QoS active on QFI %d", qfi))
		}
		p.mu.Lock()
		p.rx = p.access.leg.gnb.DownlinkQFICount(p.access.leg.session.DLTEID, qfi) - p.rxBase
		p.mu.Unlock()
		packet := make([]byte, 32)
		packet[0] = 0x80
		packet[1] = 116
		binary.BigEndian.PutUint16(packet[2:4], seq)
		binary.BigEndian.PutUint32(packet[4:8], stamp)
		binary.BigEndian.PutUint32(packet[8:12], 1)
		seq++
		stamp += 320
		wire := scenarios.UDPPacket(netip.AddrPortFrom(stream.Local.Addr, stream.Local.Port), netip.AddrPortFrom(stream.Remote.Addr, stream.Remote.Port), packet)
		upf, err := netip.ParseAddr(p.access.leg.session.UpfAddress)
		if err != nil {
			return
		}
		if err = p.access.leg.gnb.SendGPDUWithQFI(p.access.leg.session.ULTEID, upf, qfi, wire); err == nil {
			p.tx.Add(1)
		}
	}
}

func (d *phoneDashboard) state() any {
	d.mu.Lock()
	phones := append([]*dashboardPhone{}, d.phones...)
	events := append([]phoneEvent{}, d.events...)
	ready, problem := d.ready, d.problem
	d.mu.Unlock()
	out := []any{}
	for _, p := range phones {
		p.mu.Lock()
		callState, ended := "idle", ""
		if p.call != nil {
			callState = p.call.State().String()
			if p.call.State() == testue.CallTerminated {
				ended = p.call.End().String()
			}
		}
		var flows []uint8
		if servicesEnabled() {
			flows = p.access.leg.flows()
		}
		registered := false
		imsIP := ""
		if p.ims != nil {
			registered = p.ims.State().Registered
			imsIP = p.endpoint.Local.String()
		}
		rx := p.rx
		qfis := make([]int, len(flows))
		for i, flow := range flows {
			qfis[i] = int(flow)
		}
		out = append(out, map[string]any{"id": p.id, "name": p.name, "imsi": p.endpoint.Subscriber.IMSI, "number": p.endpoint.Subscriber.MSISDN, "ip": imsIP, "internetIp": p.internetIP, "nas": p.access.ue.SMSAllowed(), "registered": registered, "call": callState, "ended": ended, "incoming": p.incoming, "peer": p.peer, "messages": append([]phoneMessage{}, p.messages...), "tx": p.tx.Load(), "rx": rx, "qfi": qfis, "error": p.errorText})
		p.mu.Unlock()
	}
	return map[string]any{"mode": phoneMode(), "ready": ready, "problem": problem, "phones": out, "events": events, "time": time.Now().UTC()}
}
func (d *phoneDashboard) action(w http.ResponseWriter, r *http.Request) {
	if origin := r.Header.Get("Origin"); origin != "" {
		u, err := url.Parse(origin)
		if err != nil || u.Host != r.Host {
			http.Error(w, "same-origin requests only", 403)
			return
		}
	}
	var req struct {
		Phone  string `json:"phone"`
		Action string `json:"action"`
		To     string `json:"to"`
		Text   string `json:"text"`
	}
	dec := json.NewDecoder(http.MaxBytesReader(w, r.Body, 4096))
	dec.DisallowUnknownFields()
	if err := dec.Decode(&req); err != nil {
		http.Error(w, "invalid request", 400)
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
	if p == nil || !ready {
		http.Error(w, "UE not ready", 409)
		return
	}
	if !servicesEnabled() {
		w.WriteHeader(http.StatusForbidden)
		_ = json.NewEncoder(w).Encode(map[string]string{"error": "IMS and SMS are disabled in internet mode"})
		return
	}
	p.op.Lock()
	defer p.op.Unlock()
	ctx, cancel := context.WithTimeout(r.Context(), 30*time.Second)
	defer cancel()
	var err error
	p.mu.Lock()
	call := p.call
	p.mu.Unlock()
	switch req.Action {
	case "register":
		err = p.ims.Register(ctx)
	case "unregister":
		if call != nil && call.State() != testue.CallTerminated {
			err = fmt.Errorf("hang up before unregistering")
		} else {
			err = p.ims.Deregister(ctx)
		}
	case "sms":
		if len([]rune(req.Text)) == 0 || len([]rune(req.Text)) > 70 {
			err = fmt.Errorf("enter 1–70 characters")
			break
		}
		if !validPhoneNumber(req.To) {
			err = fmt.Errorf("recipient must be an international number")
			break
		}
		messageID := d.next.Add(1)
		p.mu.Lock()
		p.messages = append(p.messages, phoneMessage{ID: messageID, Direction: "sent", Peer: req.To, Text: req.Text, Status: "submitting", At: time.Now().UTC()})
		p.trim()
		p.mu.Unlock()
		report, e := p.access.ue.SMS.Submit(ctx, "+15550000000", req.To, req.Text)
		err = e
		if rp, ok := report.(*sms.RPError); ok {
			err = fmt.Errorf("SMS rejected: %s", rp.Cause)
		}
		status := "accepted by SMSC"
		if err != nil {
			status = "failed"
		}
		p.mu.Lock()
		for i := range p.messages {
			if p.messages[i].ID == messageID && p.messages[i].Status != "delivered to UE" {
				p.messages[i].Status = status
			}
		}
		p.mu.Unlock()
		if err == nil && os.Getenv("PEER_URL") != "" {
			go d.trackDelivery(p, messageID, req.Text, req.To)
		}
	case "call":
		if call != nil && call.State() != testue.CallTerminated {
			err = fmt.Errorf("a call is already active")
			break
		}
		if !validPhoneNumber(req.To) {
			err = fmt.Errorf("recipient must be an international number")
			break
		}
		var c *testue.Call
		c, err = p.ims.MMTel().Invite("tel:"+req.To, testue.CallOptions{})
		if err == nil {
			p.mu.Lock()
			p.call = c
			p.incoming = false
			p.peer = req.To
			p.tx.Store(0)
			p.rxBase = 0
			p.rx = 0
			p.mu.Unlock()
			go d.media(p, c)
		}
	case "answer":
		if call == nil || !call.Incoming() {
			err = fmt.Errorf("no incoming call")
		} else {
			err = call.Answer(ctx)
		}
	case "hangup":
		if call == nil || call.State() == testue.CallTerminated {
			err = fmt.Errorf("no active call")
		} else if call.State() == testue.CallConfirmed {
			err = call.Bye(ctx)
		} else if call.Incoming() {
			err = call.Reject(486)
		} else {
			err = call.Cancel(ctx)
		}
	default:
		http.Error(w, "unknown action", 400)
		return
	}
	p.mu.Lock()
	p.errorText = ""
	if err != nil {
		p.errorText = err.Error()
	}
	p.mu.Unlock()
	if err != nil {
		d.event(p.id, req.Action+": "+err.Error())
		w.WriteHeader(http.StatusConflict)
		_ = json.NewEncoder(w).Encode(map[string]string{"error": err.Error()})
		return
	}
	d.event(p.id, req.Action+" succeeded")
	_ = json.NewEncoder(w).Encode(map[string]bool{"ok": true})
}
func validPhoneNumber(s string) bool {
	if len(s) < 3 || len(s) > 16 || s[0] != '+' {
		return false
	}
	for _, c := range s[1:] {
		if c < '0' || c > '9' {
			return false
		}
	}
	return true
}

func ServePhones(address string) error {
	if address == "" {
		address = ":8080"
	}
	if os.Getenv("CORE_N2") == "" || os.Getenv("N3_ADDRESS") == "" || os.Getenv("POD_IP") == "" {
		return fmt.Errorf("CORE_N2, N3_ADDRESS and POD_IP are required")
	}
	if phoneMode() != "internet" && phoneMode() != "internet-ims-sms" {
		return fmt.Errorf("invalid UE_MODE: %s", phoneMode())
	}
	d := &phoneDashboard{phones: []*dashboardPhone{}, events: []phoneEvent{}}
	mux := http.NewServeMux()
	mux.HandleFunc("GET /api/state", func(w http.ResponseWriter, r *http.Request) {
		w.Header().Set("Content-Type", "application/json")
		w.Header().Set("Cache-Control", "no-store")
		_ = json.NewEncoder(w).Encode(d.state())
	})
	mux.HandleFunc("POST /api/action", func(w http.ResponseWriter, r *http.Request) {
		w.Header().Set("Content-Type", "application/json")
		d.action(w, r)
	})
	mux.HandleFunc("POST /api/browse", d.browse)
	d.browserRoutes(mux)
	mux.HandleFunc("GET /enhancements.js", func(w http.ResponseWriter, r *http.Request) {
		w.Header().Set("Content-Type", "application/javascript; charset=utf-8")
		w.Header().Set("Cache-Control", "no-cache")
		io.WriteString(w, strings.ReplaceAll(enhancementsJS, "['1','2']", phoneIDs()))
	})
	mux.HandleFunc("GET /healthz", func(w http.ResponseWriter, r *http.Request) { io.WriteString(w, "ok") })
	mux.HandleFunc("GET /", func(w http.ResponseWriter, r *http.Request) {
		if r.URL.Path != "/" {
			http.NotFound(w, r)
			return
		}
		w.Header().Set("Content-Type", "text/html; charset=utf-8")
		w.Header().Set("X-Content-Type-Options", "nosniff")
		w.Header().Set("Content-Security-Policy", "default-src 'self'; script-src 'self' 'unsafe-inline'; style-src 'self' 'unsafe-inline'; frame-ancestors 'none'")
		page := strings.ReplaceAll(phoneHTML, "['1','2']", phoneIDs())
		if id := os.Getenv("PHONE_ID"); id != "" {
			other := "B"
			if id == "2" {
				other = "A"
			}
			page = strings.Replace(page, "phoneMarkup('1','Phone A','B')+phoneMarkup('2','Phone B','A')", fmt.Sprintf("phoneMarkup(%q,%q,%q)", id, os.Getenv("PHONE_NAME"), other), 1)
			page = strings.ReplaceAll(page, "Register both phones", "Register phone")
			page = strings.ReplaceAll(page, "Two subscribers. One private network.", "One subscriber. Your private network.")
			page = strings.Replace(page, "</style>", ".phones{grid-template-columns:minmax(270px,390px);justify-content:center}.sidebar{display:none}.shell{grid-template-columns:1fr}.main{max-width:900px;width:100%;margin:auto}</style>", 1)
		}
		if !servicesEnabled() {
			page = strings.Replace(page, "<body>", "<body class=\"internet-only\">", 1)
			page = strings.ReplaceAll(page, "Your network, in your hands.", "Your mobile data connection.")
			page = strings.ReplaceAll(page, "Register your phones, make an IMS call, or send a message.<br>Every action travels through your live Ella Core.", "Browse and test connectivity through your UE’s internet PDU session.")
			page = strings.ReplaceAll(page, "Lab simulator · Calls use synthetic RTP test packets; browser microphone and speaker audio are not connected. Messages are real NAS SMS through Ella SMSC. Session history resets when this simulator restarts.", "Internet-only simulator · Website traffic and DNS use this UE’s data session. IMS and SMS are disabled.")
		}
		io.WriteString(w, page)
	})
	go d.initialize()
	server := &http.Server{Addr: address, Handler: mux, ReadHeaderTimeout: 5 * time.Second, ReadTimeout: 10 * time.Second, WriteTimeout: 40 * time.Second, IdleTimeout: 60 * time.Second, MaxHeaderBytes: 16384}
	log.Printf("UE phone dashboard listening on %s", address)
	return server.ListenAndServe()
}
