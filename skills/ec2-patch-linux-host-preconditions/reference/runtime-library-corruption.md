# Runtime library corruption (NSS segfault, locale, corrupt Python stdlib)

## NSS libfreeblpriv3.so corruption — yum/dnf/curl SEGFAULT
**Signatures:** every yum/dnf/curl command exits with Segmentation fault (139); `/var/log/messages`
or `dmesg` shows "error 4 in libfreeblpriv3.so". NSS is used by anything doing TLS/signature checks,
so **yum cannot fix itself** — repair with `rpm` directly from a local package file.
```bash
dmesg | grep -i 'segfault.*libfreebl' | tail
rpm -V nss-softokn nss-softokn-freebl 2>&1 | head       # shows the corrupt file
# find local RPMs (cache), or place them via S3 (aws cli doesn't use NSS the same way):
FREEBL=$(find /tmp /var/cache -name 'nss-softokn-freebl-*.rpm' 2>/dev/null | head -1)
NSS=$(find /tmp /var/cache -name 'nss-softokn-[0-9]*.rpm' 2>/dev/null | head -1)
[ -n "$FREEBL" ] && [ -n "$NSS" ] && rpm -ivh --force "$FREEBL" "$NSS"   # bypasses yum
yum clean all; yum repolist 2>&1 | tail            # should no longer segfault
```
No local RPM? download on a healthy host (`yumdownloader nss-softokn nss-softokn-freebl`), copy via S3.
If `rpm` itself segfaults, glibc/ld may also be corrupt → volume-mount repair from another instance.

## Locale / encoding errors
```bash
locale 2>&1 | head; python3 -c 'import locale; print(locale.getpreferredencoding())' 2>&1
export LANG=C.UTF-8 LC_ALL=C.UTF-8            # unblock dnf for the session
localectl set-locale LANG=C.UTF-8 2>/dev/null; localedef -i en_US -f UTF-8 en_US.UTF-8 2>/dev/null
```

## Corrupt Python standard library (breaks dnf, which is Python)
```bash
python3 -c 'import encodings, locale, os' 2>&1        # surfaces the broken module
# reinstall the platform python via rpm if a stdlib file is corrupt (bypass dnf if dnf is broken):
rpm -Va python3 python3-libs 2>&1 | head
# then, once python runs: dnf reinstall -y python3 python3-libs
```

## Verify
```bash
dnf check-update >/dev/null 2>&1; RC=$?; [ $RC -eq 0 ] || [ $RC -eq 100 ] && echo "RUNTIME OK" || echo "still broken: $RC"
```
