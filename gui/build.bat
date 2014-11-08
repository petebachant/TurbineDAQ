echo Building GUI

call pyuic4 gui\mainwindow.ui > modules\mainwindow.py

echo Building resource file

call pyrcc4 -py3 gui\icons\resources.qrc -o modules\resources_rc.py

echo Done