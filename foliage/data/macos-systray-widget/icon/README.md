# Systray icon for Foliage macOS systray widget

The files [make_icon.bat](make_icon.bat) and [make_icon.sh](make_icon.sh) originally came from the repository [systray](https://github.com/getlantern/systray) by [Latern](https://github.com/getlantern).

Install Go, then install [2goarray](https://github.com/cratonica/2goarray) like this:

```sh
setenv GOPATH /usr/local/go
go install github.com/cratonica/2goarray@latest
```

The icon file is the 64x64 Foliage icon from the foliage/data directory. Generate the icon here like this:

```sh
./make_icon.sh icon-64.png
```

That will produce the file [iconunix.go](iconunix.go).
