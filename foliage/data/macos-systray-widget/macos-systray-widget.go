package main

import (
	"github.com/getlantern/systray"
	"macos-systray-widget/icon"
)

func main() {
	onExit := func() { }
	systray.Run(onReady, onExit)
}

func onReady() {
	systray.SetTemplateIcon(icon.Data, icon.Data)
	systray.SetTooltip("Foliage")
	mQuit := systray.AddMenuItem("Quit", "Quit Foliage")
	go func() {
		<-mQuit.ClickedCh
		systray.Quit()
	}()
}
