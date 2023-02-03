# TurbineDAQ Makefile

app: ui
	python turbinedaq.py

ui:
	python -m PyQt5.uic.pyuic gui/mainwindow.ui -o modules/mainwindow.py
	python -m PyQt5.pyrcc_main gui/icons/resources.qrc -o modules/resources_rc.py
	# Replace relative import in resources file
	sed -i 's/import resources_rc/from . import resources_rc/g' modules/mainwindow.py
