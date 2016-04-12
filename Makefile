# TurbineDAQ Makefile

app: gui
	python turbinedaq.py

gui:
	python -m PyQt4.uic.pyuic.py gui/mainwindow.ui -o modules/mainwindow.py
	pyrcc4 -py3 gui/icons/resources.qrc -o modules/resources_rc.py
	# Replace relative import in resources file
	sed -i 's/import resources_rc/from . import resources_rc/g' tow/mainwindow.py
