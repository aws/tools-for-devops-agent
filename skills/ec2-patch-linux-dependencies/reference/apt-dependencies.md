# APT broken / unmet dependencies, held & pinned packages (Ubuntu/Debian)

**Signatures:** "The following packages have unmet dependencies", "Depends: libX (>= v) but v is to
be installed", "E: Broken packages", "Held broken packages", "You might want to run 'apt
--fix-broken install'", "dependency problems prevent configuration of <pkg>", "The following
packages have been kept back" for security patches.

## Diagnose
```bash
apt-get check 2>&1
dpkg --audit 2>&1
apt-mark showhold 2>&1                 # held packages
cat /etc/apt/preferences.d/* 2>/dev/null   # pinning
dpkg -l | grep -E '^iU|^iF|^iH|^rc'   # broken/half-configured
```

## Fix (least-destructive first)
```bash
apt-get update
apt-get install -f -y            # auto fix-broken
dpkg --configure -a              # finish half-configured
# 'kept back' security pkgs are usually a hold or pin:
HELD=$(apt-mark showhold); [ -n "$HELD" ] && apt-mark unhold $HELD
# a pin in /etc/apt/preferences.d/ can block the required dependency — review and adjust/remove
```

## Escalate aggressiveness only if needed
```bash
apt-get -s upgrade 2>&1 | tail        # simulate first
apt-get dist-upgrade -y               # more aggressive; MAY remove packages
# PPA is the cause:
# ppa-purge <ppa>       # revert to official packages
# force a specific compatible version:
# apt-get install <pkg>=<version>
```

## Verify
```bash
apt-get check 2>&1 && dpkg --audit 2>&1 && apt-get -s upgrade 2>&1 | tail -3 && echo "APT DEPENDENCIES OK"
```

## Escalation
- Identify the cascade root: `apt-cache depends --installed <pkg>`.
- Severe: `dpkg --force-remove-reinstreq --remove <broken-pkg>` then reinstall — last resort.
- Incomplete `do-release-upgrade` left mixed state → complete or roll back the release upgrade.
