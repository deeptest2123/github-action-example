#!/usr/bin/env python3
import os, json, html, sys
from xmlrpc.client import ServerProxy

TESTLINK_URL       = os.environ["TESTLINK_URL"]
TESTLINK_DEVKEY    = os.environ["TESTLINK_DEVKEY"]
TESTLINK_PROJECTID = int(os.environ["TESTLINK_PROJECT_ID"])
TESTLINK_REQSPECID = int(os.environ["TESTLINK_REQSPEC_ID"])

EVENT_PATH         = os.environ.get("GITHUB_EVENT_PATH")
REPO_FULLNAME      = os.environ.get("GITHUB_REPOSITORY", "repo")

if not EVENT_PATH or not os.path.exists(EVENT_PATH):
    print("No GitHub event payload; exiting (local run?).")
    sys.exit(0)

with open(EVENT_PATH, "r", encoding="utf-8") as f:
    event = json.load(f)

if event.get("action") not in {"opened", "edited", "reopened"} or "issue" not in event:
    print(f"Action {event.get('action')} not handled, exiting.")
    sys.exit(0)

issue = event["issue"]
number = issue["number"]
title  = issue["title"] or f"Issue #{number}"
body   = issue.get("body") or ""
url    = issue["html_url"]

# Build dynamic fields for TestLink
docid = f"GH-{number}"
# Make a simple HTML scope from the issue body and link
scope_html = (
    f"<p>{html.escape(body).replace(chr(10), '<br>')}</p>"
    f"<p>Source: <a href='{html.escape(url)}'>{html.escape(url)}</a></p>"
)

# Defaults; tweak via labels if you want:
#   label "tests:N"   => expected_coverage = N
#   label "reqtype:X" => type name to id mapping (keep default 3 for 'Use Case')
#   label "reqstatus:D|F|R|V" => Draft/Finish/Review/Valid etc.
labels = [lbl["name"] for lbl in issue.get("labels", [])]

expected_coverage = 1
for lbl in labels:
    if lbl.lower().startswith("tests:"):
        try:
            expected_coverage = int(lbl.split(":",1)[1])
        except: pass

# Requirement type (TL installs often map 3 => 'Use Case'); keep your org’s mapping here
req_type = 3

status_map = {"draft":"D", "finish":"F", "review":"R", "valid":"V"}
status_code = "D"
for lbl in labels:
    key = lbl.split(":",1)[-1].strip().lower() if "reqstatus:" in lbl.lower() else lbl.lower()
    if key in status_map:
        status_code = status_map[key]; break

# Compose params for XML-RPC
params = {
    "devKey":         TESTLINK_DEVKEY,
    "testprojectid":  TESTLINK_PROJECTID,
    "reqspecid":      TESTLINK_REQSPECID,
    "title":          title,
    "docid":          docid,
    # TestLink names the description field "scope" in the UI; API accepts description/scope as content
    "scope":          scope_html,
    "status":         status_code,        # e.g. "D" draft, "F" finish
    "type":           req_type,           # e.g. 3 for Use Case (adjust if your instance differs)
    "expected_coverage": expected_coverage,
}

# If the issue was edited, allow overwriting the existing requirement (same docid)
overwrite = event.get("action") in {"edited", "reopened"}
if overwrite:
    params["overwrite"] = True

server = ServerProxy(TESTLINK_URL)
try:
    # create (or overwrite) requirement
    # Note: XML-RPC namespace is usually 'tl' for TestLink
    result = server.tl.createRequirement(params)
    print("TestLink response:", result)
except Exception as e:
    print("ERROR calling TestLink XML-RPC:", e)
    sys.exit(1)
