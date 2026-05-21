# Windows installer for Foliage

Foliage for Windows is distributed as an MSI installer package.

- The MSI is built in GitHub Actions by `.github/workflows/windows-build.yml`.
- The workflow builds `dist/win/Foliage.exe` using PyInstaller and then packages it into an MSI using WiX.
- The WiX source file is generated from `dev/installers/windows/Product.wxs.tmpl` by `dev/installers/windows/create-wix-script.py`.

For local builds, run the same metadata generation and PyInstaller steps first, then run WiX (`candle` and `light`) against the generated `Product.wxs` file.

