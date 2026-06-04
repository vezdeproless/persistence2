from __future__ import annotations

SOFTWARE_BRANCHES: tuple[str, ...] = (
    "Classes",
    "Microsoft\\Active Setup\\Installed Components",
    "Microsoft\\Command Processor",
    "Microsoft\\Ctf\\LangBarAddin",
    "Microsoft\\Internet Explorer\\Extensions",
    "Microsoft\\Netsh",
    "Microsoft\\Office",
    "Microsoft\\Office test\\Special\\Perf",
    "Microsoft\\Windows CE Services\\AutoStartOnConnect\\MicrosoftActiveSync",
    "Microsoft\\Windows CE Services\\AutoStartOnDisconnect\\MicrosoftActiveSync",
    "Microsoft\\Windows NT\\CurrentVersion",
    "Microsoft\\Windows\\CurrentVersion",
    "Microsoft\\Windows\\Windows Error Reporting\\Hangs",
    "Policies\\Microsoft\\Windows\\Control Panel\\Desktop",
    "Policies\\Microsoft\\Windows\\System\\Scripts",
    "Wow6432Node\\Microsoft\\Windows\\CurrentVersion",
    "Wow6432Node\\Microsoft\\Windows NT\\CurrentVersion",
)

SYSTEM_BRANCHES: tuple[str, ...] = (
    "ControlSet001\\Control\\BootVerificationProgram",
    "ControlSet001\\Control\\Lsa\\Notification Packages",
    "ControlSet001\\Control\\Lsa\\OSConfig\\Security Packages",
    "ControlSet001\\Control\\Lsa\\Security Packages",
    "ControlSet001\\Control\\NetworkProvider\\Order",
    "ControlSet001\\Control\\Print\\Environments",
    "ControlSet001\\Control\\Print\\Monitors",
    "ControlSet001\\Control\\SafeBoot",
    "ControlSet001\\Control\\ServiceControlManagerExtension",
    "ControlSet001\\Control\\Session Manager",
    "ControlSet001\\Control\\Terminal Server\\Wds\\rdpwd",
    "ControlSet001\\Control\\Terminal Server\\WinStations\\RDP-Tcp",
    "ControlSet001\\Services",
    "Setup",
)

NTUSER_BRANCHES: tuple[str, ...] = (
    "Software\\Microsoft",
    "Software\\Policies\\Microsoft\\Windows\\System\\Scripts",
    "Software\\Wow6432Node\\Microsoft\\Windows\\CurrentVersion",
    "Software\\Wow6432Node\\Microsoft\\Windows NT\\CurrentVersion",
    "System\\CurrentControlSet\\Control",
    "System\\CurrentControlSet\\Services",
    "System\\Setup",
    "Environment",
    "Control Panel\\Desktop",
)

USRCLASS_BRANCHES: tuple[str, ...] = ("ROOT",)

TARGET_BRANCHES: dict[str, tuple[str, ...]] = {
    "SOFTWARE": SOFTWARE_BRANCHES,
    "SYSTEM": SYSTEM_BRANCHES,
    "NTUSER": NTUSER_BRANCHES,
    "USRCLASS": USRCLASS_BRANCHES,
}
