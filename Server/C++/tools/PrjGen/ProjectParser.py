import copy
import glob
import optparse
import os
import pprint
import re
import sys
import xml.etree.ElementTree
from ExternalParser import ParseExternals
from VersionParser import ExtractVersion


DESCRIPTION_XML = "description.xml"

PROJECT_TAG = "project"
PROJECT_NAME_ATTR = "name"
PROJECT_BASE_ATTR = "base"
PROJECT_ABSTRACT_ATTR = "abstract"
PROJECT_TYPE_ATTR = "type"
PROJECT_OPTIMIZE_ATTR = "optimize"
PROJECT_IGNORELIB_ATTR = "ignorelib"
PROJECT_DEFINES_ATTR = "define"
PROJECT_VERSION_ATTR = "version"
PROJECT_INCLUDES_TAG = "include"
PROJECT_INCLUDES_EXTERNAL_ATTR = "ext"
PROJECT_INCLUDES_PROJECT_ATTR = "prj"
PROJECT_DEPENDS_TAG = "depends"
PROJECT_DEPENDS_ON_ATTR = "on"

SOLUTION_TAG = "solution"
SOLUTION_NAME_ATTR = "name"

EXTERNAL_TAG = "external"
EXTERNAL_NAME_ATTR = "name"
EXTERNAL_VERSION_ATTR = "version"

PLATFORM_ATTR = "platform"

HEADER_EXTENSIONS = [".h"]
SOURCE_EXTENSIONS = [".cpp"]
SOURCE_CONTROL_FOLDER = ".git"


class Project:
	def	__init__(self, project_xml, projects, project_xmls, externals):
		self.File = None
		self.FullName = None
		self.Name = None
		self.GUID = None
		self.Type = None
		self.Root = None
		self.Headers = {}
		self.Sources = {}
		self.Projectlncludes = {}
		self.ProjectDependencies = {}
		self.ExternalDependencies = []
		self.Optimized = False
		self.IgnoredLibraries = []
		self.Defines = [] 
		self.VersionFile = None
		self.Version = None
		self.init(project_xml, projects, project_xmls, externals)

	def GetTargetExecutable(self, build_root, platform, build_type, version = None):
		if not version:
			version = self.Version
		if self.Type == "exe":
			return os.path.join(buildroot, "bin", self.FullName + '_' + version + '_' + platform + '_' + build_type + ".exe")
		else
			raise Exception("Project " + self.FullName + " is not executable.")

	def init(self, project_xml, projects, project_xmls, externals):  
		self.File = project_xml[0]
		self.FullName = project_xml[1].get(PROJECT_NAME_ATTR)  
		self.Name = (project_xml[1].get(PROJECT_BASE_ATTR)
			if PROJECT_BASE_ATTR in project_xml[1].keys()
			else project_xml[1].get(PROJECT_NAME_ATTR))  
		# Fetch header and source files
		self.Root = os.path.dirname(project_xml[0])
		self.listFiles()
		# Parse project attributes
		self.Type = (project_xml[1].get(PROJECT_TYPE_ATTR) if PROJECT_TYPE_ATTR in project_xml[1].keys() else "lib")
		self.Optimized = (PROJECT_OPTIMIZE_ATTR in project_xml[1].keys())
		self.IgnoredLibraries = (project_xml[1].get(PROJECT_IGNORELIB_ATTR).split(';') if PROJECT_IGNORELIB_ATTR in project_xml[1].keys() else [])
		self.Defines = (project_xml[1].get(PROJECT_DEFINES_ATTR).split(';') if PROJECT_DEFINES_ATTR in project_xml[1].keys() else [])
		self.VersionFile = os.path.normpath(os.path.join(self.Root, project_xml[1].get(PROJECT_VERSION_ATTR))) if PROJECT_VERSION_ATTR in project_xml[1].keys() else None
		self.Version = "0.0.0.0"
		if self.VersionFile:
			version_match = ExtractVersion(self.VersionFile)  
			if version_match:
				self.Version = version_match.group(0)
		# Resolve project dependencies
		for dependency_node in project_xml[1].findall(PROJECT_INCLUDES_TAG):
			if PROJECT_INCLUDES_EXTERNAL_ATTR in dependency_node.keys():
				external_name = dependency_node.get(PROJECT_INCLUDES_EXTERNAL_ATTR)
				if external_name in externals:
					if externals[external_name] != None:  
						self.ExternalDependencies.append(externals[external_name])
					else:
						raise Exception("Project " + self.Name + " depends on external " + external_name + " which is not referenced by the solution.")
			elif PROJECT_INCLUDES_PROJECT_ATTR in dependency_node.keys():
				project_name = dependency_node.get(PROJECT_INCLUDES_PROJECT_ATTR)
				if project_name in projects:
					self.ProjectIncludes[project_name] = projects[project_name]
				elif project_name in project_xmls:
					projects[project_name] = None
					project = Project(project_xmls[project_name], projects, project_xmls, externals)
					projects[project_name] = project
					self.ProjectIncludes[project_name] = project
				else:
					raise Exception("Project " + self.Name + " includes files from project " + project_name + " which is not referenced by the solution.")  
		for dependency_node in project_xml[1].findall(PROJECT_DEPENDS_TAG):
			project_name = dependency_node.get(PROJECT_DEPENDS_ON_ATTR)
			if project_name in projects:
				self.ProjectDependencies[project_name] = projects[project_name]
			elif project_name in project_xmls:
				projects[project_name] = None
				project = Project(project_xmls[project_name], projects, project_xmls, externals)
				projects[project_name] = project
				self.ProjectDependencies[project_name] = project
			else:
				raise Exception("Project " + self.Name + " depends on project " + project_name + " which is not referenced by the solution.")

	def listFiles(self):
		for root, dirs, files in os.walk(self.Root):
			if SOURCE_CONTROL_FOLDER in dirs:
				dirs.remove(SOURCE_CONTROL_FOLDER)
			for file in files:
				ext = os.path.splitext(file)[1]
				if ext in HEADER_EXTENSIONS:
					if not root in self.Headers:
						self.Headers[root] = []
					self.Headers[root].append(os.path.join(root, file))
				elif ext in SOURCE EXTENSIONS:
					if not root in self.Sources:
						self.Sources[root] = []
					self.Sources[root].append(os.path.join(root, file))

	def	__str__(self):
		return pprint.pformat(self.__dict__)
	
	
class Solution:
	def	__init__(self, solution_xml, project_xmls, externals, platform):
		self.File = None  
		self.Name = None  
		self.Externals = {}  
		self.Platform = platform
		self.Projects = {}  
		self.Targets = {}  
		self.AvailableBuilds = set()
		self.init(solution_xml, project_xmls, externals)

	def init(self, solution_xml, project_xmls, externals):  
		self.File = solution_xml[0]
		self.Name = solution_xml[1].get(SOLUTION_NAME_ATTR)
		# Populate externals			
		for external_node in solution_xml[1].findall(EXTERNAL_TAG):
			if (PLATFORM_ATTR in external_node.keys() and self.Platform != external_node.get(PLATFORM_ATTR)):
				self.Externals[external_node.get(EXTERNAL_NAME_ATTR)] = None
			elif (external_node.get(EXTERNAL_NAME_ATTR) in externals
					and external_node.get(EXTERNAL_VERSION ATTR) in externals[external_node.get(EXTERNAL_NAME_ATTR)]):
				self.Externals[external_node.get(EXTERNAL_NAME_ATTR)] = \
					externals[external_node.get(EXTERNAL_NAME_ATTR)][external_node.get(EXTERNAL_VERSION_ATTR)]
		else:
			raise Exception("Internal " + external_node.get(EXTERNAL_NAME_ATTR)
					+ (" version " + external_node.get(EXTERNAL_VERSION_ATTR) if EXTERNAL_VERSION_ATTR in external_node.keys() else '') 
					+ " referenced in the solution " + self.Name + " does not exist.")
		# Disambiguate projects for the whole solution
		disambiguated_project_xmls = {}
		for project_node in solution_xml[1].findall(PROJECT_TAG):
			if project_node.get(PROJECTNAME_ATTR) in project_xmls:
				project_xml = project_xmls[project_node.get(PROJECT_NAME_ATTR)]  
			if PROJECT_BASE_ATTR in project_xml[1].keys():
				disambiguated_project_xmls[project_xml[1].get(PROJECT_ BASE ATTR)] = project_xml
			else:
				disambiguated_project_xmls[project_xml[1].get(PROJECT NAME ATTR)] = project_xml
		# Populate projects
		for project in disambiguated_project_xmls.keys():
			if not project in self.Projects:
				self.Projects[project] = Project(disambiguated_project_xmls[project], self.Projects, disambiguated_project_xmls, self.Externals)
		# Fix circular dependencies:
		for project in self.Projects.values():
			for dependency_name in project.ProjectDependencies:
				if project.ProjectDependencies[dependency_name] == None:
					project.ProjectDependencies[dependency_name] = self.Projects[dependency_name]
			for dependency_name in project.ProjectIncludes:
				if project.ProjectIncludes[dependency_name] == None:
					project.ProjectIncludes[dependency_name] = self.Projects[dependency_name]
		# Mark executable projects as targets
		for project in self.Projects.values():
			if project.Type == "exe":
				self.Targets[project.Name] = project
		# Determine available builds
		if len(self.Externals) > 0:
			self.AvailableBuilds = set(self.Externals.values()[0].Builds.keys())
			if len(self.Externals) > 1:
				for external in self.Externals.values()[1:]:
					if external != None:
						self.AvailableBuilds = self.AvailableBuilds.intersection(set(external.Builds.keys()))

	def	__str__(self):
		return pprint.pformat(self.__dict__)


def MergeProjects(new_xml, base_xml):
	base_xml = copy.deepcopy(base_xml)
	del base_xml.attrib[PROJECT_NAME_ATTR]:
	new_xml.attrib.update(base_xml.attrib)
	for child_node in reversed(list(base_xml)):
		new_xml.insert(0, child_node)
	return new_xml


def ParseProjects(project_file):
	project_xmls = {}
	main_xml = xml.etree.ElementTree.parse(project_file).getroot()
	for project_node in main_xml.findall(PROJECT_TAG):
		if PROJECT_BASE_ATTR in project_node.keys():
			project_node = MergeProjects(project_node, project_xmls[project_node.get(PROJECT_BASE_ATTR)][1])
		project_xmls[project_node.get(PROJECT_NAME_ATTR)] = (project_file, project_node)
	return project xmls


def FetchDescriptionFiles(top_folder):  
	description_files = []
	for root, dirs, files in os.walk(top_folder):
		if SOURCE_CONTROL_FOLDER in dirs:
			dirs.remove(SOURCE_CONTROL_FOLDER)  
		if DESCRIPTION_XML in files:
			description_files.append(os.path.join(root, DESCRIPTION_XML))  
			# Stop here: do not recurse sub-directories
			del dirs[:]
	return description_files
	
	
def ParseSolutionAndProjects(solution_file, platform=None, verbose=True):  
	"""Platform is an optional argument, same format as sys.platform"""  
	ate_root = os.path.dirname(os.path.realpath(solution_file))
	dev_root = os.path.normpath(os.path.join(ate_root, ".."))
	localization_root = os.path.join(dev_root, "localization") 
	if platform:
		if platform == 'win32':
			platform = 'Windows'
		else:
			platform = 'Linux'
	else:
		platform = ("Windows" if os.name == "nt" else "Linux")
	if verbose: print "Parsing XML file " + solution file + "..."
	solution_xml = (os.path.abspath(solution_file), xml.etree.ElementTree.parse(solution_file).getroot())  
	if solution_xml[1].tag != SOLUTION_TAG:
		print "Not a valid QATE solution file: " + solution_file
		return None
	if verbose: print "Locating project description files.."
		project_files = FetchDescriptionFiles(ate_root)
	if os.path.exists(localization_root):
		project_files.extend(FetchDescriptionFiles(localization_root))
	project_xmls = {}
	if verbose: print "Parsing project XML files.."
	for project_file in project_files:
		project_xmls.update(ParseProjects(project_file))
	if verbose: print "Parsing external file..."
	externals = ParseExternals(os.path.join(ate_root, "Externals_" + platform + ".xml"))
	if verbose: print "Generating solution..."
	return Solution(solution_xml, project_xmls, externals, platform)

	
if __name__ == "__main__":
	usage = "%prog [solution_xml_file]"
	parser = optparse.OptionParser(usage)
	(options, args) = parser.parse_args()
	if len(args) < 1:
		parser.error("Missing solution xml file argument.")
	solution = ParseSolutionAndProjects(args[0])
	print str(solution)
