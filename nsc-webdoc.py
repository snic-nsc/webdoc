#!/usr/bin/env python
# ***********************************************************
#  File: nsc-webdoc[.py]
#  Description: a tool for generation software documentation
#               based on README files in a directory tree.
#  Author: Peter Larsson
#  Affiliation: National Supercomputer Centre,
#               Linkoping University, Sweden.
# ***********************************************************

import os
import copy
import sys
import re
import commands
import yaml
from optparse import OptionParser
from mako.template import Template
from collections import defaultdict

class Tree(defaultdict):
	# Beware! defaultdict hack to make a tree
	def __init__(self, value = None):
		super(Tree, self).__init__(Tree)
		self.value = value

def splitdir(path):
	head = path
	result = []
	while (head != "" and head != "/"):
		(head,tail) = os.path.split(head)
		result.append(tail)

	return result[::-1]

def add_node(tree,nodes):
	if len(nodes) == 0:
		return
	else:
		add_node(tree[nodes[0]],nodes[1:])

def generate_tree(files,basepath):
	result = Tree()

	for file in sorted(files):
		# Drop first part of basepath
		leafname = file[len(basepath):]
		leafname = splitdir(basepath)[-1] + leafname

		# Drop last node because this is the "README.NSC"
		nodes = splitdir(leafname)[:-1]
		add_node(result,nodes)

	return result

def split_payload(data):
	payload = data.strip().split("\n")

	# Check if a Markdown title is given
	# NB: Markup dependency!

	# Try to determine extent of metadata section
	lastline = len(payload)
	for (i,line) in enumerate(payload):
		if line.upper().find("BEGIN METADATA") != -1:
			lastline = i

	if lastline == 0:
		title = ""
		offset = 0
	else:
		title = payload[0]
		offset = 2
		# Strip markdown formatting if there
		if title[0:2] == "# ":
			offset = 1 
			title = title[3:]

	content="\n".join(payload[offset:lastline])
	return (title,content)

def extract_metadata(filename):
	if os.path.exists(filename):
		data = open(filename,"r").readlines()

		metadata_start = 0
		for counter, line in enumerate(data):
			if line.upper().strip() == "--- BEGIN METADATA ---":
				metadata_start = counter

		metadata_end = 0
		for counter, line in enumerate(data):
			if line.upper().strip() == "--- END METADATA ---":
				metadata_end = counter

		if (metadata_end - metadata_start) > 1:
			metadata = data[metadata_start+1:metadata_end]
			return yaml.load("\n".join(metadata))
		else:
			return dict()
	else:
		return dict()

def metadata_match(metadb,query):
	result = True
	for (key,val) in query.iteritems():
		if key not in metadb:
			result = False
			return result 
		else:
			# Is this a YAML list?
			if type(metadb[key]) == list:
				# Check all elements in the list
				found = False
				for i in metadb[key]:
					if type(i) == str:
						if i.lower() == val.lower():
							found = True
					else:
						if i == val:
							found = True
				
				if not found:
					result = False
					return result

			else:
				# No list
				if metadb[key] != val:
					result = False
					return result

	return result

def generate_doc(tree,toplevel,basepath,path,level,breadcrumb,metadb,system):
	basename = toplevel.keys()[0]

	if path != "":
		leafname = splitdir(path)[-1]
	else:
		leafname = basename

	if options.verbose:
		print "---"

	# Calculate path to README file for this node
	if path == "":
		filename = (basepath + "/" + "README.NSC")
	else:
		filename = (basepath + path + "/" + "README.NSC")
	
	if options.verbose:
		print "Input : ", filename

	# Construct output HTML name
	sysname = system.lower()
	if path == "":
		docname = sysname + "-" + basename + ".html"
	else:
		docname = sysname + "-" + basename + "-" + (path[1:] + ".html").replace("/","-")

	bclink = docname
	docname = "output/" + docname

	if options.verbose:
		print "Output: ", docname

	# Generate breadcrumb
	bc = breadcrumb + [(leafname,bclink)]

	# Read markdown
	if os.path.exists(filename):
		readme_md = open(filename,"r").read()
		# Split file into h1 heading + rest
		# TODO: make smarter splitting procedure
		(status,payload) = commands.getstatusoutput("multimarkdown %s" % filename)

		if filename in metadb:
			file_metadata = metadb[filename]
		else:
			# No metadata
			# print "No metadata, I was looking for", filename
			file_metadata = {}

	else:
		if options.verbose:
			print "Making generic README for %s, because the corresponding file was not found." % (filename)

		payload = open("static/README.placeholder","r").read()
		file_metadata = extract_metadata("static/README.placeholder")

	# Collect data for navigation menu
	if tree == {}:
		versionlist=[]
	else:
		# Construct list of link to sublevels
		versionlist = []
		for v in tree.keys():
			metadataname = basepath + path + "/" + v
			linkname = sysname + "-" + basename + path + "/" + v

			version_metadata = extract_metadata(metadataname+"/README.NSC")
			linkname = linkname.replace("/","-")+".html"

			if "description" in version_metadata:
				description = version_metadata["description"]
			else:
				description = "N/A"
			versionlist.append((v,linkname,description))

	# Chunk up the README file into title & content & metadata
	(title,content) = split_payload(payload)
	if title=="":
		# No title given
		# FIXME: have to add HTML title here
		title = "<h1>" + leafname + "</h1>"

	output = open(docname,"w")

	# Render page from template
	template = Template(filename="static/README.template",input_encoding="utf-8",output_encoding="utf-8",default_filters=['decode.utf8'])
	html = template.render(pagename=leafname,payload1=title,payload2=content,tree=toplevel,basename=basename,versions = sorted(versionlist),level=level,breadcrumb=bc,metadata=file_metadata,system=system)
	
	# Custom postprocessing
	html = html.replace("<table>","<table class=\"table table-striped table-condensed\">")

	# Save HTML output
	output.write(html)
	output.close()

	if options.verbose:
		print "Saved : ", docname,"to disk."

	# Proceed deeper in the tree
	for (name,version) in tree.iteritems():
		generate_doc(version,toplevel,basepath,path + "/" + name,level+1,bc,metadb,system)

# Main program

parser = OptionParser()
parser.add_option("-v","--verbose",dest="verbose",help="Print extra info",action="store_true")
parser.add_option("-d","--dryrun",dest="dryrun",help="Don't actually do anything",action="store_true")
parser.add_option("-s","--system",dest="system",help="Generate documentation for a specific system")
parser.add_option("-r","--rebuild",dest="rebuild",help="Scan file system and rebuild file name cache.",action="store_true")
(options,args) = parser.parse_args()

# Check for multimarkdown
(status,payload) = commands.getstatusoutput("multimarkdown -v")
if status != 0:
	print "I need the multimarkdown command in $PATH to generate HTML files! Please install it or update $PATH."
	sys.exit(1)
else:
	if options.verbose:
		print "Multimarkdown command detected"

# Establish /software base directory
basedir = args[0].strip()
if basedir[-1] == "/":
	# Strip trailing slash
	basedir = basedir[0:-1]

# Expand to absolute path
if basedir[0] != "/":
	# Relative path
	basedir = os.path.abspath(basedir)

if not os.path.exists(basedir):
	print "It seems like the give path to a software installation directory %s, does not exist." % (basedir)
	sys.exit(1)

# Find documentation files
if os.path.exists("filenames.cache") and not options.rebuild:
	if options.verbose:
		print "Using cached paths to documentation files."
	readmes = open("filenames.cache","r").read().strip()
	readmes = readmes.split("\n")
else:
	if options.verbose:
		print "Searching for documentation files in", basedir
	(status,readmes) = commands.getstatusoutput("find %s -maxdepth 5 -name README.NSC" % (basedir))

	readmes = readmes.split("\n")
	# Dirty hack to remove e.g. permission errors for find command
	# these mess up the parsing of filenames. There could be more like this...
	readmes = filter(lambda x: x[0:6] != "find: ",readmes)
	readmes.sort()
	
	# Create cache file
	if len(readmes) >= 1 and readmes[0] != '':
		if not options.dryrun:
			if options.verbose:
				print "Writing the cache file \"filenames.cache\"."
			readmecache = open("filenames.cache","w")
			readmecache.write("\n".join(readmes)+"\n")
			readmecache.close()

		if status != 0:
			print "There was a problem searching the indicated path for README files."
			print "I will continue working with what I have."
	else:
		print "Found no documentation files. Exiting."
		sys.exit(1)

if options.verbose:
	print "Found",len(readmes),"documentation files!"
	for f in readmes:
		print f
	print
	print "Scanning metadata in..."

# Collect metadata
metadata = {}
for readme in readmes:
	if options.verbose:
		print "%s:" % (readme)

	file_metadata = extract_metadata(readme)
	if file_metadata != {}:
		metadata[readme] = file_metadata 
		if options.verbose:
			for (key,value) in file_metadata.items():
				print " *",key, ":", value

	if options.verbose:
		print

# Construct filter for system based on command line flag
if options.system:
	query={ "systems" : options.system}
	system_name = query["systems"]
else:
	query={}
	system_name = "all"

# Filter file list based on metadata
filtered_readmes = []
for readme in readmes:
	if readme in metadata:
		file_metadata = metadata[readme]
		if metadata_match(file_metadata,query):
			filtered_readmes.append(readme)
		else:
			if options.verbose:
				print "Skipping",readme,"due to search parameters."
	else:
		# Inclusive mode: files without metadata matches any query. Is this good?
		filtered_readmes.append(readme)

# Walk directory tree of the software distribution and build a tree structure
software = generate_tree(files = filtered_readmes,basepath=basedir)

# Find name of root because it might not be "software"
tree_root = software.keys()[0]

if options.verbose:
	print "Identified the root of the software tree as '%s'." % (tree_root)
	print
	print "The first two levels in the software tree:"
	for (category,apps) in software[tree_root].iteritems():
		print category
		for (app,version) in apps.iteritems():
			print " *",app

	print

if not options.dryrun:
	if options.verbose:
		print "Making web site..."

	#Recursively scan program tree and generate documentation
	for key in software.iterkeys():
		generate_doc(tree=software[key],toplevel=software,basepath=basedir,path="",level=1,breadcrumb=[],metadb=metadata,system=system_name)
