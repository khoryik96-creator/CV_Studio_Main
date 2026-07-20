Optional Antiword support for legacy .doc extraction

CV Studio can extract old binary Microsoft Word .doc files without Antiword using its native fallback. Antiword is optional and only used for .doc files.

Windows installer behaviour from v24.6.73:
- First checks vendor/antiword, C:\Program Files\Antiword, C:\Program Files (x86)\Antiword, C:\antiword, ANTIWORDHOME, and PATH.
- If not found, tries to download the trusted CRAN/rOpenSci Windows antiword package and install it to C:\Program Files\Antiword.
- If download/install fails, setup continues and native .doc extraction remains active.

Manual install option:
Place antiword.exe in C:\Program Files\Antiword\, or place an antiword.zip / antiword folder beside INSTALL.bat and rerun INSTALL.bat.
