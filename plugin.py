from Plugins.Plugin import PluginDescriptor
from Screens.Screen import Screen
from Screens.MessageBox import MessageBox
from Components.SelectionList import SelectionList
from Components.Sources.StaticText import StaticText
from Components.Label import Label
from Components.ActionMap import ActionMap
import xml.dom.minidom as xml
from urllib import quote
from urllib2 import Request, URLError, urlopen
from httplib import HTTPException
from enigma import eDVBDB

class LiveStreamingLinks(Screen):
	LIST_NAME = 0
	LIST_CAT = 1
	LIST_TYPE = 2
	LIST_URL = 3

	LEVEL_FILES = 0
	LEVEL_XML = 1

	DIR_ENIGMA2 = '/etc/enigma2/'
	URL_BASE = 'http://et-live-links.googlecode.com/svn/trunk/'

	skin = """
	<screen position="c-300,c-210" size="600,420" title="">
		<widget name="list" position="10,10" size="e-20,205" scrollbarMode="showOnDemand" />
		<widget source="info" render="Label" position="10,215" size="e-20,200" halign="center" valign="top" font="Regular;17" />
		<ePixmap pixmap="skin_default/buttons/red.png" position="c-150,e-45" size="140,40" alphatest="on" />
		<ePixmap pixmap="skin_default/buttons/green.png" position="c-0,e-45" size="140,40" alphatest="on" />
		<widget source="key_red" render="Label" position="c-150,e-45" zPosition="1" size="140,40" font="Regular;20" halign="center" valign="center" backgroundColor="#9f1313" transparent="1" />
		<widget source="key_green" render="Label" position="c-0,e-45" zPosition="1" size="140,40" font="Regular;20" halign="center" valign="center" backgroundColor="#1f771f" transparent="1" />
	</screen>"""

	def __init__(self, session):
		self.skin = LiveStreamingLinks.skin
		Screen.__init__(self, session)
		self["key_red"] = StaticText(_("Cancel"))
		self["key_green"] = StaticText(_("Download"))
		self["actions"] = ActionMap(["SetupActions", "ColorActions"],
		{
			"ok": self.keyOk,
			"save": self.keyGo,
			"cancel": self.keyCancel,
			"green": self.keyGo,
			"red": self.keyCancel,
		}, -2)
		self.list = SelectionList()
		self["list"] = self.list
		self["info"] = StaticText("")

		self.doExit = False
		self.level = self.LEVEL_FILES
		self.subMenuName = ''
		self.subMenuDescrName = ''
		self.xmlFiles = []
		self.xmlCategories = []
		self.lastchanged = ''
		self.lastchanges = ''
		self.onLayoutFinish.append(self.createTopMenu)

	def initSelectionList(self):
		list = []
		self.list.setList(list)

	def createTopMenu(self):
		self.setTitle(_("ET-Livestream importer"))
		self.initSelectionList()
		self.subMenuName = ''
		self.subMenuDescrName = ''
		self.level = self.LEVEL_FILES
		self.readMainXml()
		count = 0
		for x in self.xmlFiles:
			self.list.addSelection(x[self.LIST_CAT], x[self.LIST_NAME], count, False)
			count += 1
		self["info"].setText("")

	def readXmlSubFile(self, fileName, descrName):
		self.initSelectionList()
		self.xmlList = []
		self.subMenuName = fileName
		self.subMenuDescrName = descrName
		self.level = self.LEVEL_XML
		self.readChannelXml(self.xmlList, fileName)
		tmp = _('Last update') + ': %s\n\n%s' % (self.lastchanged, self.lastchanges)
		self["info"].setText(tmp)
		count = 0
		for x in self.xmlCategories:
			self.list.addSelection(x, x, count, False)
			count += 1

	def keyOk(self):
		if self.level == self.LEVEL_FILES:
			self.keyGo()
		elif self.level == self.LEVEL_XML:
			if len(self.xmlCategories) > 0:
				self.list.toggleSelection()

	def keyGo(self):
		if self.level == self.LEVEL_FILES:
			self.readXmlSubFile(self.xmlFiles[self.list.getSelectedIndex()][self.LIST_NAME], self.xmlFiles[self.list.getSelectedIndex()][self.LIST_CAT])
			return

		self.doExit = False
		tmpList = []
		tmpList = self.list.getSelectionsList()
		if len(tmpList) == 0:
			self.session.openWithCallback(self.infoCallback, MessageBox, _("Nothing selected"), MessageBox.TYPE_INFO)
			return

		self.xmlList.sort()

		tvFileList = []
		radioFileList = []
		for item in tmpList:
			if self.createUserBouquetFile(item[1], 'tv') > 0:
				tvFileList.append((item[1]))
			if self.createUserBouquetFile(item[1], 'radio') > 0:
				radioFileList.append((item[1]))

		if len(tvFileList) > 0:
			self.createBouquetFile(tvFileList, 'tv')
		if len(radioFileList) > 0:
			self.createBouquetFile(radioFileList, 'radio')

		db = eDVBDB.getInstance()
		db.reloadServicelist()
		db.reloadBouquets()
		self.doExit = True
		self.session.openWithCallback(self.infoCallback, MessageBox, _("Finished import"), MessageBox.TYPE_INFO)

	def infoCallback(self, confirmed):
		if self.doExit:
			self.createTopMenu()

	def createBouquetFile(self, catNames, fileType):
		newFileContent = ''
		fileContent = self.readFile(self.DIR_ENIGMA2 + 'bouquets.' + fileType)

		if fileContent == '':
			return

		for x in fileContent:
			x = self.stripLineEndings(x)
			isFound = False
			for cat in catNames:
				if '\"userbouquet.streamlinks' + self.convertToFileName(self.subMenuName + cat) in x:
					isFound = True
					break
			if not isFound:
				newFileContent += x + '\n'

		for cat in catNames:
			newFileContent += '#SERVICE 1:7:1:0:0:0:0:0:0:0:FROM BOUQUET \"userbouquet.streamlinks' + self.convertToFileName(self.subMenuName + cat) + '.' + fileType +'\" ORDER BY bouquet\n'

		fp = open(self.DIR_ENIGMA2 + 'bouquets.' + fileType, 'w')
		fp.write(newFileContent)
		fp.close()

	def createUserBouquetFile(self, catName, fileType):
		ret = 0
		newChannelList = []
		newChannelList.append('#NAME Livestream ' + self.subMenuDescrName + ' ' + catName)
		for x in self.xmlList:
			if x[self.LIST_CAT] == catName and x[self.LIST_TYPE] == fileType:
				newChannelList.append('#SERVICE 4097:0:0:0:0:0:0:0:0:0:%s:%s' % (quote(x[self.LIST_URL]), quote(x[self.LIST_NAME])))
				ret += 1

		if ret > 0:
			fp = open(self.DIR_ENIGMA2 + 'userbouquet.streamlinks' + self.convertToFileName(self.subMenuName + catName) + '.' + fileType, 'w')
			for x in newChannelList:
				fp.write(x + '\n')
			fp.close()
		return ret

	def keyCancel(self):
		if self.level == self.LEVEL_FILES:
			self.close()
		elif self.level == self.LEVEL_XML:
			self.createTopMenu()

	def wgetUrl(self, target):
		std_headers = {
			'User-Agent': 'Mozilla/5.0 (X11; U; Linux x86_64; en-US; rv:1.9.2.6) Gecko/20100627 Firefox/3.6.6',
			'Accept-Charset': 'ISO-8859-1,utf-8;q=0.7,*;q=0.7',
			'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
			'Accept-Language': 'en-us,en;q=0.5',
		}
		outtxt = Request(target, None, std_headers)
		try:
			outtxt = urlopen(target).read()
		except (URLError, HTTPException), err:
			return ''
		return outtxt

	def readFile(self, name):
		try:
			lines = open(name).readlines()
			return lines
		except:
			return ''
			pass

	def convertToFileName(self, name):
		return name.replace(' ', '_')

	def stripLineEndings(self, buf):
		return buf.strip('\r\n').strip('\n').strip('\t')

	def getText(self, nodelist):
		rc = []
		for node in nodelist:
			if node.nodeType == node.TEXT_NODE:
				rc.append(node.data)
			return str(''.join(rc))

	def readMainXml(self):
		xmlnode = []

		url = self.URL_BASE + 'livestreams.xml'
		lines = self.wgetUrl(url)
		if lines == '':
			return
		xmlnode = xml.parseString(lines)

		self.xmlFiles = []
		tmp = xmlnode.getElementsByTagName("xmlfile")
		for i in range(len(tmp)):
			name = self.stripLineEndings(self.getText(tmp[i].getElementsByTagName("name")[0].childNodes))
			cat = self.stripLineEndings(self.getText(tmp[i].getElementsByTagName("descr")[0].childNodes))
			self.xmlFiles.append((name, cat))

	def readChannelXml(self, tmpList, fileName):
		xmlnode = []

		url = self.URL_BASE + fileName + '.xml'
		lines = self.wgetUrl(url)
		if lines == '':
			return
		xmlnode = xml.parseString(lines)

		self.xmlCategories = []
		tmp = xmlnode.getElementsByTagName("stream")
		for i in range(len(tmp)):
			name = self.stripLineEndings(self.getText(tmp[i].getElementsByTagName("name")[0].childNodes))
			url = self.stripLineEndings(self.getText(tmp[i].getElementsByTagName("url")[0].childNodes))
			cat = self.stripLineEndings(self.getText(tmp[i].getElementsByTagName("cat")[0].childNodes))
			type = self.stripLineEndings(self.getText(tmp[i].getElementsByTagName("type")[0].childNodes))
			tmpList.append((name, cat, type, url))

			foundCat = False
			for x in self.xmlCategories:
				if x == cat:
					foundCat = True
					break
			if not foundCat:
				self.xmlCategories.append((cat))

		tmp = xmlnode.getElementsByTagName("comments")
		if len(tmp) == 1:
			self.lastchanged = self.stripLineEndings(self.getText(tmp[0].getElementsByTagName("lastchange")[0].childNodes))
			self.lastchanges = self.stripLineEndings(self.getText(tmp[0].getElementsByTagName("description")[0].childNodes))


def main(session, **kwargs):
	session.open(LiveStreamingLinks)

def Plugins(**kwargs):
	return [PluginDescriptor(name = _("ET-Livestream"), description = _("Download streaming links from the internet"), where = PluginDescriptor.WHERE_EXTENSIONSMENU, fnc = main)]
