# SELinux/AppArmor denials, PAM/PBIS, post-patch service restarts

## SELinux / AppArmor blocking package scriptlets
**Signatures:** "SELinux is preventing", "avc: denied", "%post scriptlet failed" with an AVC in
audit.log, "restorecon: unable to set security context", AppArmor DENIED in journal.
```bash
getenforce 2>/dev/null; ausearch -m AVC -ts recent 2>/dev/null | tail
# restore contexts if the file_contexts DB / labels are off:
restorecon -Rv /var/lib/rpm /var/lib/dpkg /usr/lib /usr/bin 2>&1 | tail
# update the policy package (temporarily permissive), then RE-ENFORCE:
setenforce 0; dnf update -y selinux-policy selinux-policy-targeted 2>&1 | tail; setenforce 1
# persistent specific denial -> scoped policy module (better than disabling):
ausearch -m AVC -ts today | audit2allow -M patch_fix && semodule -i patch_fix.pp
# AppArmor: set the denied profile to complain for the patch, then re-enforce:
# aa-complain <profile>  ... patch ...  aa-enforce <profile>
```
**Do not leave SELinux permissive / AppArmor in complain mode.**

## PAM / PBIS auth misconfig blocking operations
```bash
grep -Rl pbis /etc/pam.d/ 2>/dev/null
# a broken PAM stack can block sudo/scriptlet operations; validate the config and restore a known-good
# /etc/pam.d entry (PBIS/AD-join issues have their own vendor tooling: /opt/pbis/bin/...).
```

## systemd service won't restart after its package updated
```bash
systemctl --failed --no-legend | awk '{print $1}'
systemctl daemon-reload
systemctl restart <service>; systemctl status <service> --no-pager -l | tail
journalctl -u <service> --no-pager -n 30
```

## Verify
```bash
getenforce 2>/dev/null   # expect Enforcing
ausearch -m AVC -ts recent 2>/dev/null | grep -c denied
systemctl --failed --no-legend | wc -l   # expect 0
```

## Escalation
- Persistent AVC → keep the scoped `audit2allow` module; don't disable SELinux fleet-wide.
- PBIS/AD problems → vendor tooling / re-join; out of scope for a package fix.
- Service still failing post-patch → capture `journalctl -u <svc>`; may be a config-format change in the new package version.
