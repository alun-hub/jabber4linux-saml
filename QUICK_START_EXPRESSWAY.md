# Quick Start - Expressway SAML (5 Minutes)

This is the **recommended** configuration for production Jabber4Linux deployments.

## Prerequisites

✅ Cisco Expressway-E reachable from your network
✅ Expressway-C configured with HTTP proxy to CUCM
✅ CUCM with SAML SSO enabled
✅ Keycloak (or other IdP) configured

## 1. Install Dependencies

```bash
# Debian/Ubuntu
sudo apt install python3-pyqt6 python3-pyqt6.qtwebengine

# Or via pip
pip install PyQt6 PyQt6-WebEngine
```

## 2. Clone and Setup

```bash
git clone https://github.com/alun-hub/jabber4linux-saml.git
cd jabber4linux-saml
git checkout claude/saml-keycloak-jabber-Gj2kD

pip install -r requirements.txt
```

## 3. Add Certificates (if self-signed)

```bash
mkdir -p ~/.config/jabber4linux/server-certs/

# Export Expressway-E certificate
openssl s_client -connect YOUR-EXPRESSWAY-E:8443 -showcerts </dev/null 2>/dev/null | \
  openssl x509 -outform PEM > ~/.config/jabber4linux/server-certs/expressway-e.pem
```

## 4. Test Connection

```bash
python3 test_saml_auth.py --server YOUR-EXPRESSWAY-E --port 8443 --interactive --debug
```

**Expected result:**
```
TEST 1: Basic HTTPS Connectivity                  ✓ PASS
TEST 2: SAML Endpoint                             ✓ PASS
TEST 3: UDS API Endpoint                          ✓ PASS
TEST 4: DNS Discovery                             ✓ PASS (or ⚠ optional)
TEST 5: Interactive SAML                          ✓ PASS
```

## 5. Start Jabber4Linux

```bash
python3 -m jabber4linux --debug
```

### Login Configuration:

```
┌─────────────────────────────────────────┐
│ Server: [expressway-e.example.com    ] │ ← Your Expressway-E
│ Port:   [8443                         ] │ ← Usually 8443
│                                         │
│ Authentication:                         │
│ ○ Username/Password                     │
│ ● SAML SSO                              │ ← Select this
│                                         │
│ ☑ Connecting via Expressway (MRA)      │ ← Check this
│                                         │
│ [Login with SAML]  [Exit]               │
└─────────────────────────────────────────┘
```

**Click "Login with SAML":**
- Browser opens
- Redirects to Keycloak
- Log in with your credentials
- Browser closes automatically
- Jabber4Linux starts!

## Troubleshooting

### Problem: "SAML Endpoint Not Found" (HTTP 404)

The SAML endpoint `/ssosp/saml/login` is not accessible on Expressway-E. This is a **server configuration issue**.

The Expressway-C administrator must configure HTTP Proxy:

```
Expressway-C → Applications → Unified Communications → HTTP Proxy
  Status: Enabled

  HTTP Server 1: <CUCM hostname>:<port>

  HTTP Allowed Paths:
    /ssosp     → CUCM
    /cucm-uds  → CUCM

  Cookie Passthrough: Enabled
  Session Stickiness: Enabled
```

Also verify in CUCM Admin → System → SAML Single Sign-On:
- SAML SSO: Enabled
- Entity ID: `https://expressway-e.example.com:8443` (Expressway-E address, NOT CUCM)

### Problem: "Connection refused"

```bash
# Check Expressway is reachable
ping YOUR-EXPRESSWAY-E
curl -k https://YOUR-EXPRESSWAY-E:8443/
```

### Problem: "No CUCM session cookies"

**Most common issue!** Check cookie domain in CUCM:

```
CUCM Admin → System → SAML SSO → Entity ID
Should be: https://expressway-e.example.com:8443  ← Expressway, not CUCM!
```

### Problem: SSL Certificate Error

```bash
# Add Expressway certificate
openssl s_client -connect YOUR-EXPRESSWAY-E:8443 -showcerts </dev/null 2>/dev/null | \
  openssl x509 -outform PEM > ~/.config/jabber4linux/server-certs/expressway-e.pem

# Restart Jabber4Linux
python3 -m jabber4linux --debug
```

### Still Having Issues?

**See comprehensive guides:**
- `EXPRESSWAY_SAML_DEBUG.md` - Expressway-specific debugging
- `SAML_DEBUGGING_GUIDE.md` - General SAML troubleshooting
- `EXPRESSWAY_SETUP.md` - Complete Expressway configuration

**Run diagnostics:**
```bash
python3 test_saml_auth.py --server YOUR-EXPRESSWAY-E --interactive --debug > test.log 2>&1
```

## DNS Auto-Discovery (Optional but Recommended)

```dns
_collab-edge._tls.example.com. IN SRV 0 0 8443 expressway-e.example.com.
```

**With DNS configured:**
- Server field auto-fills with Expressway address
- "Connecting via Expressway (MRA)" auto-checked
- No manual configuration needed!

**Test DNS:**
```bash
dig _collab-edge._tls.example.com SRV
```

## Why Expressway?

**Advantages over Direct CUCM:**
- ✅ Works from anywhere (office, home, mobile)
- ✅ No VPN required
- ✅ Better security (DMZ architecture)
- ✅ Single configuration for all locations
- ✅ Standard Cisco recommendation
- ✅ Required for mobile devices

**When to use Direct CUCM:**
- Internal network only
- No remote access needed
- Testing/development

## Next Steps

After successful login:
1. ✓ Make/receive calls
2. ✓ Check corporate directory
3. ✓ Test voicemail (if configured)

## Configuration Reference

**Expressway-C:**
```
Applications → Unified Communications → HTTP Proxy
- HTTP Proxy: Enabled
- HTTP server 1: cucm.example.com
- Paths: /ssosp, /cucm-uds
```

**CUCM:**
```
User Management → User Settings → SAML SSO
- SAML SSO: Enabled
- IdP Metadata: Keycloak metadata imported
- Entity ID: https://expressway-e.example.com:8443
```

**Keycloak:**
```
Clients → CUCM-SAML
- Client Protocol: saml
- Valid Redirect URIs: https://expressway-e.example.com:8443/*
- UID attribute: Mapped
```

## Success Indicators

**In debug output you should see:**
```bash
:: Found Expressway via DNS: expressway-e.example.com:8443
:: SAML client configured for Expressway-C proxy
:: URL changed: https://keycloak.../auth/realms/...
:: Cookie received: JSESSIONID
:: Cookie received: JSESSIONIDSSO
:: Authentication complete with 2 CUCM cookies
✓ Authentication successful!
```

---

**That's it! You're ready to use Jabber4Linux with Expressway SAML.** 🎉

For issues, check: `EXPRESSWAY_SAML_DEBUG.md`
