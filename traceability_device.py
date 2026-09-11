"""Visitor-reported device metadata is analytics-only, never identity or location."""


def device_details(user_agent="", mobile_hint="", platform_hint="", metadata=None):
    metadata = metadata or {}
    reported_agent = str(metadata.get("user_agent") or "").strip()[:1000]
    if reported_agent:
        user_agent = reported_agent
        # Proxy-server client hints must not override a visitor-reported agent.
        mobile_hint = ""
        platform_hint = ""
    ua = user_agent.casefold()
    if "ipad" in ua or "tablet" in ua or ("android" in ua and "mobile" not in ua):
        device_type = "tablet"
    elif mobile_hint == "?1" or any(value in ua for value in ("mobile", "iphone", "android")):
        device_type = "mobile"
    elif any(value in ua for value in ("windows", "macintosh", "linux", "cros")):
        device_type = "desktop"
    else:
        device_type = "unknown"

    if "edg/" in ua:
        browser = "Microsoft Edge"
    elif "opr/" in ua or "opera" in ua:
        browser = "Opera"
    elif "firefox/" in ua or "fxios/" in ua:
        browser = "Firefox"
    elif "chrome/" in ua or "crios/" in ua:
        browser = "Google Chrome"
    elif "safari/" in ua:
        browser = "Safari"
    else:
        browser = "Unknown"

    if platform_hint:
        operating_system = platform_hint
    elif "windows" in ua:
        operating_system = "Windows"
    elif "android" in ua:
        operating_system = "Android"
    elif "iphone" in ua or "ipad" in ua or "ios" in ua:
        operating_system = "iOS"
    elif "mac os" in ua or "macintosh" in ua:
        operating_system = "macOS"
    elif "linux" in ua:
        operating_system = "Linux"
    else:
        operating_system = "Unknown"
    reported_type = str(metadata.get("device_type") or "").lower().strip()
    if reported_type in {"mobile", "tablet", "desktop"}:
        device_type = reported_type
    for key in ("browser", "operating_system"):
        value = str(metadata.get(key) or "").strip()[:120]
        if value and value.lower() != "unknown":
            if key == "browser":
                browser = value
            else:
                operating_system = value
    return {
        "device_type": device_type,
        "browser": browser,
        "operating_system": operating_system,
        "user_agent": user_agent[:1000],
    }

