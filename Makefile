# TurbineDAQ Makefile

app:
	python turbinedaq/main.py

ui:
	python -m PyQt5.uic.pyuic gui/mainwindow.ui -o turbinedaq/mainwindow.py
	# Replace relative import in resources file
	sed -i 's/import resources_rc/from . import resources_rc/g' turbinedaq/mainwindow.py

ui-resources:
	python -m PyQt5.pyrcc_main gui/icons/resources.qrc -o turbinedaq/resources_rc.py

black:
	black -l79 \
	    turbinedaq/main.py \
		turbinedaq/runtypes.py \
		turbinedaq/daqtasks.py \
		turbinedaq/vectasks.py \
		turbinedaq/acsprgs.py
