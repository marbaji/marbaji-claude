---
name: domain-check
description: Check domain-name availability locally via RDAP (rdap.org) with a whois fallback, no MCP or registrar quota required. Use when the user wants to check whether one or more domains are registered (e.g. "is mybrand.com taken", "/domain-check", brainstorming a company/product name). Runs entirely from the terminal via curl and the system `whois` binary.
---

# Domain Availability Checker

Checks domain-name availability without burning any registrar API quota. Uses **RDAP via `rdap.org`** as the primary lookup (the modern, JSON-based replacement for WHOIS that all major TLDs now expose), and **falls back to the system `whois`** for any domain that hits an RDAP rate-limit or connection failure.

## Why this exists

Registrar MCPs (GoDaddy, Namecheap connectors) impose anonymous shared daily quotas that are easy to burn through during a naming session. RDAP is a public protocol with no auth and no quota for casual use — `rdap.org` aggregates and forwards to the right registry per TLD.

## Requirements

- `curl` — preinstalled on macOS/Linux
- `whois` — preinstalled on macOS; `apt install whois` / `brew install whois` if missing
- (Nothing else — no MCP, no API key, no registrar account)

## Default TLD policy

Unless the user specifies otherwise:

- **Default to `.com` only.** It's the only TLD that matters for most B2B SaaS naming, and it's the hardest to find free — so it's the highest-signal check.
- If the user explicitly asks for `.ai`, `.io`, `.co`, etc., add those.
- If the user says "any TLD" or "all TLDs", check `.com .ai .io .co .app`.

## Instructions

### Step 1 — Build the domain list

Take the candidate names from the user. For each name, build `<name>.<tld>` for every requested TLD.

### Step 2 — Run the parallel RDAP check

```bash
DOMAINS=(name1.com name2.com name3.com)  # populate with full domain list

check_one() {
  local domain=$1
  local code=$(curl -sL -o /dev/null -w "%{http_code}" --max-time 10 "https://rdap.org/domain/${domain}")
  case $code in
    404) echo "AVAILABLE  $domain" ;;
    200) echo "TAKEN      $domain" ;;
    429) echo "RATELIMIT  $domain" ;;
    000) echo "TIMEOUT    $domain" ;;
    *)   echo "UNKNOWN($code) $domain" ;;
  esac
}
export -f check_one

printf '%s\n' "${DOMAINS[@]}" | xargs -P 10 -I {} bash -c 'check_one "$@"' _ {} | sort
```

- `-P 10` runs 10 in parallel — keeps `rdap.org` from rate-limiting too aggressively while still being fast.
- `--max-time 10` prevents one slow upstream from stalling the batch.
- Sort the output for a clean table.

### Step 3 — Retry RATELIMIT / TIMEOUT entries via whois

For any domain that came back `RATELIMIT` (429) or `TIMEOUT` (000), retry sequentially via `whois`:

```bash
RETRY=(domain1.com domain2.com)  # populate from RATELIMIT/TIMEOUT rows

for d in "${RETRY[@]}"; do
  out=$(whois "$d" 2>&1)
  if echo "$out" | grep -qiE "no match|not found|no entries found|no object found|no data found|status: free|status: available"; then
    echo "AVAILABLE  $d"
  elif echo "$out" | grep -qiE "registrar:|creation date:|registry domain id|registered on"; then
    echo "TAKEN      $d"
  else
    echo "UNCLEAR    $d"
  fi
done
```

Sequential is fine here because the retry list is usually small (3-10 items) and `whois` rate-limits per-server.

### Step 4 — Present results to the user

Output a clean table sorted by status (AVAILABLE first), then `.com` alphabetically, then any other TLDs. Example:

```
| Domain          | Status    |
|-----------------|-----------|
| mybrand.com     | AVAILABLE |
| coolname.com    | AVAILABLE |
| acme.com        | TAKEN     |
| widget.com      | TAKEN     |
```

If 0 are available across the full list, say so explicitly and offer next steps:
1. Generate more candidate names (coined / multi-syllable / 2-word combos)
2. Drop the `.com` constraint and check `.ai`, `.io`, `.co`
3. Consider a registered name available for purchase via a domain broker (real but expensive — typically $5K–$50K+ for short clean `.com`s)

## Notes & caveats

- **`TAKEN` ≠ "in use".** Many short clean `.com`s are squatted by domain investors and listed for sale. RDAP can't distinguish "active business" from "parked-for-sale." If the user is curious about a specific name, suggest they visit the URL in a browser to see what's there.
- **`AVAILABLE` is high-confidence but not 100%.** Registry latency is rare but real — a domain registered 5 minutes ago may still show as `AVAILABLE` until RDAP propagates. Always re-verify on the registrar's checkout page before paying.
- **`.ai` quirks.** The `.ai` registry (NIC.AI, run by Anguilla) sometimes returns slow or partial RDAP responses. Whois fallback is more reliable for `.ai` than for `.com`.
- **No purchase capability.** This skill only *checks* availability. To register, point the user to Cloudflare Registrar (cheapest, no markup) or Namecheap.

## Example triggers

- "Check if foo.com is available"
- "/domain-check mybrand cool startup"
- "Is veridon.ai taken?"
- "Run domain availability on this list: x, y, z"
- "Brainstorm 10 names for X and check which `.com`s are free"
