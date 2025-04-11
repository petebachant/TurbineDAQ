.PHONY: app ui ui-resources format build

app:
	uv run turbinedaq

ui:
	uv run python -m PyQt5.uic.pyuic gui/mainwindow.ui -o turbinedaq/mainwindow.py
	# Replace relative import in resources file
	sed -i 's/import resources_rc/from . import resources_rc/g' turbinedaq/mainwindow.py

ui-resources:
	uv run python -m PyQt5.pyrcc_main gui/icons/resources.qrc -o turbinedaq/resources_rc.py

format:
	uvx ruff format turbinedaq

build:
	@uv run pyinstaller turbinedaq/main.py \
	--onedir \
	--noconsole \
	--noconfirm \
	--name turbinedaq \
	--add-data "gui/icons:gui/icons" \
	--icon gui/icons/turbinedaq.png
