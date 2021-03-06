import VersionUpdater 
import getpass
import glob 
import multiprocessing 
import optparse
import os
import subprocess 
import sys
import temp file 
import traceback

ATE_FOLDER = "ate"
LOCALIZATION FOLDER = "localization"
TOOLS_FOLDER = "tools"
UI_FOLDER = os.path.join("atenet2.0", "nate")
GIT_REPOSITORY_HTTP = 'https://horizon.bankofamerica.com/scm/scm/qate.git' # TODO: use QateEnv() instead but need to fix python path because when we call NightlyBuild.py the package path is messed up
GIT_REPOSITORY_SSH = 'ssh://git@horizon.bankofamerica.com/qate/qate.git'    # TODO: use QateEnv() instead but need to fix python path because when we call NightlyBuild.py the package path is messed up
GIT_REPOSITORY = GIT_REPOSITORY_SSH if getpass.getuser() in ["ammbld", "qateuat"] else GIT_REPOSITORY_HTTP

def SendEMail(to, pwd, failed, build, log, build_log): 
	try:
	print "Attempting to send e-mail..." 
	sys.path.append(os.path.normpath(os.path.join(pwd, "..","..", "python")))
	import mail
	import socket
	host = socket.getfqdn()
	amm = mail.AutoMailMaker()
	amm.From = "dg.qate_dev@baml.com"
	amm.ToList = [to]
	if len(failed) > 0:
		amm.Subject = "Nightly Build ({build}) FAILED".format(build = build)
		amm.Text = "Nightly Build from\n{pwd}\nfailed for the following solutions on host {host}:\n\n".format(pwd = pwd, host = host) 
		for solution in failed:
			amm.Text += "- {solution}\n".format(solution = solution)
		#amm.Attachments = [log, build_log]
	else:
		amm.Subject = "Nightly Build ({build}) SUCCESS".format(build = build)
		amm.Text = "Nightly Build from\n{pwd}\ncompleted successfulLy.\n\n".format(pwd = pwd, host = host)
	amm.send()
	except:
	traceback.print_exc()
	print "Unable to send e-mail."

def CheckoutTag(iTag, iPlatform):
	tmp_dir = tempfile.mkdtemp(prefix='qate')
	git_checkout_commandline = ("git", "clone", "-b", iTag, "--single-branch", "--depth", "1", GIT_REPOSITORY, tmp_dir]
	print ''.join(git_checkout_commandline)
	if iPlatform == "Windows":
		git_checkout_commandline = ''.join(git_checkout_commandline)
	subprocess.check_call(git_checkout_commandline)

	git_log_commandline =["git", "log"]
	if iPlatform == "Windows":
		git_log_commandline = ' '.join(git_log_commandline) 
	subprocess.check_call(git_log_commandline, cwd=tmp_dir)
	
	return tmp_dir

def UpdateFromGit(iFolder, iRevert):
	if (iRevert):
		print "Reverting folder " + iFolder + "..."
		git_commandline = ["git", "checkout", "--", iFolder]
		subprocess.check_call(git_commandline)
	print "Pulling from Git..."
	git_commandline = ["git", "pull"]
	subprocess.check_call(git_commandline)
	print "Done."

def BuildSolutionWindows(iSolution, iBuildType, iPerformPackaging, iLogFilename): 
	if iSolution is None:
		print 'solution UNDEFINED!!!!'
		exit(0)

	print "Building solution " + iSolution
	if iPerformPackaging:
	iBuildType = iBuildType.replace("Release", "Package") 
	iBuildType = iBuildType.replace('_', '|') 
	os.environ['MSBUILDDISABLENODEREUSE'] = '1'
	vsPath = os.environ["VS90COMNTOOLS"]
	if vsPath is None:
		print 'No visual studio path set in env variable VS9COMMNTOOLS' 
		exit(0)
	build_commandline = '"%s" "%s" /build "%s"' % (os.path.join(vsPath, "..", "IDE", "devenv.com"), iSolution, iBuildType);
	if iLogFilename is not None:
		build_commandline += '/out "%s"' % iLogFilename
	print build_commandline
	subprocess.check_call(build_commandline)

def BuildSolution_Linux(iSolution, iBuildRoot, iBuildType, iPerformPackaging, iLogFile):
	for target in iSolution.Targets.values():
		Makefile = target.FullName + '_' +  iBuildType + ".mk"
		print "Building Makefile " + Makefile
		build_commandline = ["make", "-f", Makefile, "package" if iPerformPackaging else "build", "-j", str(multiprocessing.cpu_count())]
		subprocess.check_call(build_commandline, cwd=iBuildRoot, stdout=iLogFile, stderr=iLogFile)

def BuildSolutions(iDevRoot, iXMLFiles, iBuildRoot, iBuildType, iPerformPackaging, iPerformLibraryPackaging, iNightlyMode, iLogFilename, iBuildLogFilename, oFailed): 
	log = None
	build_log = None
	if iLogFilename != None and iBuildLogFilename != None:
		# Open log files
		log = open(iLogFilename, 'w')
		build_log = open(iBuildLogFilename, 'w')
		if platform == "Windows":
			build log.close()

	packages = []
	libs = {)
	for xml_file in iXMLFiles:
		# Iterate through all solution XML files
		build_root = iBuildRoot
		solution = None
		tmp_dir = None
		try:
			# Parse solution
			solution = ProjectParser.ParseSolutionAndProjects(xml_file) 
			if not solution:
				continue
			if iNightlyMode == "official": 
				# Official build:
				# - Look for tag existence,
				# - Checkout the tag in a temporary folder,
				# - Parse the solution there (files may have changed)
				# handle case of projects with different configurations 
				targetName = solution.Name
				if targetName == "TradeManager":
					targetName = "TM"
				elif targetName.startswith("FHProxy"):
					targetName = "FHProxy"
				elif targetName.startswith("Trader"):
					targetName = "Trader"

				version = VersionUpdater.GetLatestTaggedVersion(targetName) 
				print "Latest tagged version detected " + version
				tag = "{0}_{1}".format(targetName, version)
				print "Target name=" + targetName + " and version is " + version 
				print "Tag to checkout is " + tag

				tmp_dir = CheckoutTag(tag, platform)
				solution = ProjectParser.ParseSolutionAndProjects(solution.File.replace(iDevRoot, tmp_dir)) 
				build_ root = os.path.join(tmp_dir, "build")
			# Generate build system
			# and initiate solution build
			tools_folder = os.path.join(iDevRoot, TOOLS_FOLDER)
			if platform == "Windows":
				from VS2015Generator import GenerateVS2015Files
				BuildSolution_Windows(GenerateVS2015Files(solution, build_root, tools_folder), iBuildType, iPerformPackaging, iBuildLogFilename) 
			else:
				from LinuxMakeGenerator import GenerateMakefiles
				GenerateMakefiles(solution, build_root, iBuildType, tools_folder, iNightlyMode)
				BuildSolution_Linux(solution, build_root, iBuildType, iPerformPackaging, build_log)
			if iNightlyMode == "official": 
				# Official build:
				# - Transfer built packages from the temporary folder
				from package_utils import copytree
				if os.path.exists(os.path.join(build_root, "bin")):
					copytree(os.path.join(build_root, "bin"), os.path.join(iBuildRoot, "bin"))
				if os.path.exists(os.path.join(build_root, "package")):
					copytree(os.path.join(build_root, "package"), os.path.join(iBuildRoot, "package"))
			# Enqueue used libraries for later packaging
			libs.update(solution.Externals) 
		except Exception:
			# In case of exception, write the stacktrace to the Nightly.log
			traceback.print_exc(file = log) 
			if solution:
				oFailed.append(solution.Name + ' ' +  xml file)
			else:
				oFailed.append(xml_file)
		finally:
			# Official build only: clean up temporary build folder
			if tmp_dir:
				from package_utils import rmtree
				rmtree(tmp_dir)

	if iPerformPackaging and iPerformLibraryPackaging:
		# Package libraries used during the build
		for lib in libs.values():
			if lib:
				packages.append(PackageLibrary(lib, iBuildType, os.path.join(iBuildRoot, "package")))

	if build_log != None and log != None: 
		# Close log files 
		build_log.close() 
		log.close()

# Main
if name == "__main__":
	# Parse options, set up environment...
	pwd = os.path.dirname(os.path.realpath(__file__))
	log_filename = os.path.join(pwd, "Nightly.log")
	build_ log_filename = os.path.join(pwd, "Nightly.log")
	platform = ("Windows" if os.name == "nt" else "Linux") 
	dev_root = os.path.normpath(os.path.join(pwd, "..", "..")) 
	os.environ['DEV_ROOT'] = dev_root
	ate_root = os.path.join(dev_root, "ate") 
	os.environ['ATE_ROOT'] = ate_root

	if platform == "Windows":
		usage = "%prog --build=[Release_Win32] [path_to_solution_xml_1] [path_to_solution_xml_2] ..."
		parser = optparse.OptionParser(usage)
		parser.add_option("-b", "--build", action="store", dest="build", choices=["Release_Win32"], default="Release_Win32")
	else:
		usage = "%prog --build=[i686|x86_64] [path_to_solution_xml_1] [path_to_solution_xml_2] ..."
		parser = optparse.OptionParser(usage)
		parser.addoption("-b", "--build", action="store", dest="build", choices=["i686", "x86_641, default="i686")
	parser.add_option("--dont-package", action="store_false", dest="package", default=True)
	parser.add_option("--dont-package-libraries", action="store_false" dest="packace_libraries", default=True)
	parser.add_option("—dont-git-update", action="store_false", dest="git_update", default=True)
	parser.add_option("--git-revert", action="store_true", dest="git_revert", default=False)
	parser.add_option("--mail", action="store", dest="mail")
	parser.add_option("-e", "—exclude", action="append", dest="excludes", default=[])
	parser.add_option("-o", "--output", action="store", dest="output", default=os.path.join(dev_root, "build")) 
	parser.add_option("-m", "--mode", action="store", dest="mode", choices=["nightly", "official"], default="nightly") 
	parser.add_option("--console-log", action="store_true", dest="console_log", default=False)
	(options, args) = parser.parse_args()

	build_root = options.output

	if options.console_log:
		log_filename = None
		build log filename = None

	sys.path.append(os.path.normpath(os.path.join(pwd,"..", "Packaging")))
	from PackageLibrary import PackageLibrary
	# from RegistrationGenerator import generateRegistrationFromXML 
	import ProjectParser

	# Update from GIT
	if(options.git_update):
		UpdateFromGit(ate_root, options.git_revert)

	# Build list of solutions to consider
	xml_files = []
	if len(args) == 0:
		xml files.extend(glob.glob(os.path.join(ate root, "x.xml"))) 
	else:
		for arg in args:
			xml_files.extend(glob.glob(arg))
	if (len(options.excludes) > 0):
		print options.excludes
		excluded_xmls = []
		for exclude in options.excludes: 
			excluded_xmls.extend(glob.glob(os.path.realpath(exclude))) 
		xml_files = list(set(xml_files).difference(set(excluded_xmls)))

	failed = []
	BuildSolutions(dev_root, xml_files, build_root, options.build, options.package, options.package_libraries, options.mode, log_filename, build_log_filename, failed)

	retCode = 0
	if len(failed) == 0:
		print "Build completed successfully."
	else:
		print "Errors occured during the build. Please check the error log." 
		retCode = -1
	if options.mail:
		SendEMail(options.mail, pwd, failed, options.build, log_filename, build_log_filename)

	exit(retCode)
