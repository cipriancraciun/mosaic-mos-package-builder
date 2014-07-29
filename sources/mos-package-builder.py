#!/usr/bin/python2


import json
import re
import os
import os.path as path
import subprocess
import sys
import time
import uuid


def _main (_configuration) :
	
	_descriptor = _configuration["descriptor"]
	_sources_archive = _configuration["sources"]
	_package_archive = _configuration["package"]
	_temporary = _configuration["temporary"]
	
	_package_name = _configuration["package-name"]
	_package_version = _configuration["package-version"]
	_package_release = _configuration["package-release"]
	_package_distribution = _configuration["package-distribution"]
	
	if _temporary is None :
		_temporary = path.join (path.join ("/tmp/mosaic-mos-package-builder/temporary", uuid.uuid4 () .hex))
		MkdirCommand () .execute (_temporary, True)
	if True :
		_sources_scratch = path.join (_temporary, "sources")
		_package_scratch = path.join (_temporary, "package")
	if _descriptor is None :
		_descriptor = path.join (_sources_scratch, "package.json")
	
	if True :
		_descriptor = path.realpath (_descriptor)
		_sources_archive = path.realpath (_sources_archive)
		_sources_scratch = path.realpath (_sources_scratch)
		_package_archive = path.realpath (_package_archive)
		_package_scratch = path.realpath (_package_scratch)
		_temporary = path.realpath (_temporary)
	
	_logger.info ("configuring...")
	_logger.info ("  -> descriptor: `%s`;", _descriptor)
	_logger.info ("  -> sources archive: `%s`;", _sources_archive)
	_logger.info ("  -> sources scratch: `%s`;", _sources_scratch)
	_logger.info ("  -> package archive: `%s`;", _package_archive)
	_logger.info ("  -> package scratch: `%s`;", _package_scratch)
	_logger.info ("  -> temporary: `%s`;", _temporary)
	_logger.info ("  -> package name : `%s`;", _package_name)
	_logger.info ("  -> package version : `%s`;", _package_version)
	_logger.info ("  -> package release : `%s`;", _package_release)
	_logger.info ("  -> package distribution : `%s`;", _package_distribution)
	
	os.chdir (_temporary)
	os.environ["TMPDIR"] = _temporary
	
	if os.path.exists (_sources_archive) :
		SafeZipExtractCommand () .execute (_sources_scratch, _sources_archive)
	else :
		_logger.warn ("missing sources archive `%s`; ignoring!", _sources_archive)
	
	if os.path.exists (_package_archive) :
		_logger.warn ("existing package archive `%s`; deleting!", _package_archive)
	
	_definitions = {}
	if _package_name is not None :
		_definitions["package:name"] = _package_name
	if _package_version is not None :
		_definitions["package:version"] = _package_version
	if _package_release is not None :
		_definitions["package:release"] = _package_release
	if _package_distribution is not None :
		_definitions["package:distribution"] = _package_distribution
	
	_builder = _create_builder (
			descriptor = _json_load (_descriptor),
			sources = _sources_scratch,
			package_archive = _package_archive,
			package_outputs = _package_scratch,
			temporary = _temporary,
			definitions = _definitions,
	)
	
	_prepare = _builder.instantiate ("prepare")
	_assemble = _builder.instantiate ("assemble")
	_package = _builder.instantiate ("package")
	_cleanup = _builder.instantiate ("cleanup")
	
	if False :
		_scroll = Scroll ()
		
		_builder.describe (_scroll)
		
		_scroll.append ("prepare commands:")
		_prepare.describe (_scroll.splice (indentation = 1))
		
		_scroll.append ("assemble commands:")
		_assemble.describe (_scroll.splice (indentation = 1))
		
		_scroll.append ("package commands:")
		_package.describe (_scroll.splice (indentation = 1))
		
		_scroll.append ("cleanup commands:")
		_cleanup.describe (_scroll.splice (indentation = 1))
		
		_scroll.stream (lambda _line : _logger.debug ("%s", _line))
	
	if False :
		_scroll = Scroll ()
		
		_scroll.append ("rpm specification:")
		_scroll.include_scroll (_builder._generate_rpm_spec (), indentation = 1)
		
		_scroll.stream (lambda _line : _logger.debug ("%s", _line))
	
	if os.environ.get ("__execute__") == "__true__" :
		_prepare.execute ()
		_assemble.execute ()
		_package.execute ()
		_cleanup.execute ()


class Builder (object) :
	
	def __init__ (self, _temporary, _definitions) :
		
		self._context = Context ()
		self._definitions_ = _definitions
		if self._definitions_ is None :
			self._definitions_ = {}
		
		self._temporary = PathValue (self._context, [_temporary], identifier = "execution:temporary")
		self._resource_outputs = PathValue (self._context, [self._temporary, "resources"], identifier = "execution:resources:outputs")
		self._timestamp = ConstantValue (self._context, int (time.time ()), identifier = "execution:timestamp")
		
		self._definitions = {}
		self._resources = {}
		self._overlays = []
		
		self._command_environment = {
				"TMPDIR" : self._temporary,
		}
		self._command_arguments = {
				"environment" : self._command_environment,
		}
	
	def _initialize_definitions (self, _descriptors_) :
		
		_descriptors = {}
		_descriptors.update (_descriptors_)
		_descriptors.update (self._definitions_)
		self._definitions = {}
		for _identifier in _descriptors :
			self._initialize_definition (_identifier, _json_select (_descriptors, (_identifier,), basestring))
	
	def _initialize_definition (self, _identifier, _template) :
		if _identifier in self._definitions :
			raise Exception ()
		_definition = ExpandableStringValue (self._context, _template, identifier = "definitions:%s" % (_identifier,))
		self._definitions[_identifier] = _definition
	
	def _initialize_resources (self, _descriptors) :
		for _identifier in _descriptors :
			_descriptor = _json_select (_descriptors, (_identifier,), dict)
			self._initialize_resource (_identifier, _descriptor)
	
	def _initialize_resource (self, _identifier, _descriptor) :
		
		if _identifier in self._resources :
			raise Exception ("wtf!")
		
		_generator = _json_select (_descriptor, ("generator",), basestring)
		
		if _generator == "fetcher" :
			_uri = ExpandableStringValue (self._context, _json_select (_descriptor, ("uri",), basestring), pattern = _resource_uri_re)
			_output = PathValue (self._context, [self._resource_outputs, _identifier], pattern = _normal_path_re)
			_resource = FetcherResource (self, _identifier, _uri, _output)
			
		else :
			raise Exception ("wtf!")
		
		self._resources[_identifier] = _resource
	
	def _initialize_overlays (self, _descriptors, _root) :
		for _index in xrange (len (_descriptors)) :
			self._initialize_overlay (_index, _json_select (_descriptors, (_index,), dict), _root)
	
	def _initialize_overlay (self, _index, _descriptor, _root) :
		
		_target = PathValue (self._context, [ExpandableStringValue (self._context, _json_select (_descriptor, ("target",), basestring))], pattern = _target_path_re)
		_generator = _json_select (_descriptor, ("generator",), basestring)
		
		if _generator == "unarchiver" :
			_resource = ResolvableValue (self._context, ExpandableStringValue (self._context, _json_select (_descriptor, ("resource",), basestring), pattern = _context_value_identifier_re), self.resolve_resource)
			_format = ExpandableStringValue (self._context, _json_select (_descriptor, ("format",), basestring))
			_overlay = UnarchiverOverlay (self, _root, _target, lambda : _resource () .path, _format)
			
		elif _generator == "symlinks" :
			_links = []
			for _link_target in _json_select (_descriptor, ("links",), dict) :
				_link_source = _json_select (_descriptor, ("links", _link_target,), basestring)
				_link_target = PathValue (self._context, [ExpandableStringValue (self._context, _link_target)], pattern = _target_path_re)
				_link_source = PathValue (self._context, [ExpandableStringValue (self._context, _link_source)], pattern = _normal_path_re)
				_links.append ((_link_target, _link_source))
			_overlay = SymlinksOverlay (self, _root, _target, _links)
			
		else :
			raise Exception ("wtf!")
		
		self._overlays.append (_overlay)
	
	def instantiate (self, _phase) :
		raise Exception ("wtf!")
	
	def describe (self, _scroll) :
		raise Exception ("wtf!")
	
	def _describe_definitions (self, _scroll) :
		_scroll.append ("definitions:")
		_subscroll = _scroll.splice (indentation = 1)
		if self._definitions is not None :
			for _identifier in sorted (self._definitions.keys ()) :
				_value = self._definitions[_identifier]
				if _identifier in self._definitions_ :
					_subscroll.appendf ("`%s`: `%s` (overriden);", _identifier, _value)
				else :
					_subscroll.appendf ("`%s`: `%s`;", _identifier, _value)
	
	def _describe_resources (self, _scroll) :
		_scroll.append ("resources:")
		_subscroll = _scroll.splice (indentation = 1)
		for _resource_identifier in sorted (self._resources.keys ()) :
			_resource = self._resources[_resource_identifier]
			_resource.describe (_subscroll)
	
	def _describe_overlays (self, _scroll) :
		_scroll.append ("overlays:")
		_subscroll = _scroll.splice (indentation = 1)
		for _overlay in self._overlays :
			_overlay.describe (_subscroll)
	
	def resolve_resource (self, _identifier) :
		if _identifier not in self._resources :
			raise Exception ("wtf! %s" % _identifier)
		return self._resources[_identifier]


def _create_builder (descriptor = None, **_arguments) :
	
	_schema = _json_select (descriptor, ("_schema",), basestring)
	_schema_version = _json_select (descriptor, ("_schema/version",), int)
	
	if _schema == "tag:ieat.ro,2014:mosaic:v2:mos-package-builder:descriptors:composite-package" and _schema_version == 1 :
		_builder = CompositePackageBuilder (descriptor = descriptor, **_arguments)
		
	else :
		raise Exception ("wtf!")
	
	return _builder


class CompositePackageBuilder (Builder) :
	
	def __init__ (self, descriptor = None, sources = None, package_archive = None, package_outputs = None, temporary = None, definitions = None) :
		
		Builder.__init__ (self, temporary, definitions)
		
		self._sources = PathValue (self, [sources])
		self._package_archive = PathValue (self, [package_archive])
		self._package_outputs = PathValue (self, [package_outputs])
		
		self._initialize (descriptor)
	
	def instantiate (self, _phase) :
		if _phase == "prepare" :
			return self._instantiate_prepare ()
		elif _phase == "assemble" :
			return self._instantiate_assemble ()
		elif _phase == "package" :
			return self._instantiate_package ()
		elif _phase == "cleanup" :
			return self._instantiate_cleanup ()
		else :
			raise Exception ("wtf!")
	
	def _instantiate_prepare (self) :
		_commands = []
		_commands.append (MkdirCommand (**self._command_arguments) .instantiate (self._resource_outputs))
		for _resource in self._resources.values () :
			_commands.append (_resource.instantiate ())
		return SequentialCommandInstance (_commands)
	
	def _instantiate_assemble (self) :
		_commands = []
		_commands.append (MkdirCommand (**self._command_arguments) .instantiate (self._package_outputs))
		for _overlay in self._overlays :
			_commands.append (_overlay.instantiate ())
		return SequentialCommandInstance (_commands)
	
	def _instantiate_package (self) :
		_commands = []
		_commands.append (SafeFileCreateCommand (**self._command_arguments) .instantiate (self.rpm_spec, LambdaValue (self._context, lambda : self._generate_rpm_spec () .lines_with_nl ())))
		_commands.append (self._generate_rpm_command ())
		return SequentialCommandInstance (_commands)
	
	def _instantiate_cleanup (self) :
		_commands = []
		_commands.append (ChmodCommand (**self._command_arguments) .instantiate (self._temporary, "u=rxw", True))
		_commands.append (RmCommand (**self._command_arguments) .instantiate (self._temporary, True))
		return SequentialCommandInstance (_commands)
	
	def _generate_rpm_spec (self) :
		
		_scroll = Scroll ()
		_scroll.append ("")
		
		_scroll.appendf ("name: %s", self.package_name)
		_scroll.appendf ("version: %s", self.package_version)
		_scroll.appendf ("release: %s", self.package_release)
		_scroll.appendf ("exclusivearch: %s", self.package_architecture)
		_scroll.append ("")
		# epoch
		# excludearch
		# exclusivearch
		# excludeos
		# exclusiveos
		
		_scroll.appendf ("prefix: %s", self.package_root)
		_scroll.append ("")
		
		_scroll.appendf ("buildarch: %s", self.package_architecture)
		_scroll.appendf ("buildroot: %s", self._package_outputs)
		_scroll.append ("")
		# buildrequires
		# buildconflicts
		# buildprereq
		
		# source, nosource
		# patch, nopatch
		
		_scroll.appendf ("url: %s", self.rpm_url)
		_scroll.appendf ("license: %s", self.rpm_license)
		_scroll.appendf ("summary: %s", self.rpm_summary)
		_scroll.append ("")
		# distribution
		# group
		# vendor
		# packager
		
		if len (self._rpm_provides) > 0 :
			for _rpm_provides in self._rpm_provides :
				_scroll.appendf ("provides: %s", _rpm_provides)
			_scroll.append ("")
		
		if len (self._rpm_requires) > 0 :
			for _rpm_requires in self._rpm_requires :
				_scroll.appendf ("requires: %s", _rpm_requires)
			_scroll.append ("")
		
		# conflicts
		# obsoletes
		
		_scroll.append ("autoprov: no")
		_scroll.append ("autoreq: no")
		_scroll.append ("")
		
		_scroll.append ("%description")
		_scroll.appendf ("%s", self.rpm_summary, indentation = 1)
		_scroll.append ("")
		
		_scroll.append ("%prep")
		_scroll.append ("true", indentation = 1)
		_scroll.append ("%build")
		_scroll.append ("true", indentation = 1)
		_scroll.append ("%install")
		_scroll.append ("true", indentation = 1)
		_scroll.append ("%check")
		_scroll.append ("true", indentation = 1)
		_scroll.append ("%clean")
		_scroll.append ("true", indentation = 1)
		_scroll.append ("")
		
		_scroll.append ("%files")
		_scroll.append ("%defattr(-,root,root,-)", indentation = 1)
		_scroll.appendf ("%s", self.package_root, indentation = 1)
		_scroll.append ("")
		
		# pre
		# post
		# preun
		# postun
		# verifyscript
		
		return _scroll
	
	def _generate_rpm_command (self) :
		_commands = []
		
		_true_path = _resolve_executable_path ("true")
		
		_commands.append (MkdirCommand (**self._command_arguments) .instantiate (self.rpm_outputs))
		
		_commands.append (RpmBuildCommand (**self._command_arguments) .instantiate (self.rpm_spec,
				
				rpm_macros = "/dev/null",
				rpm_buildroot = self._package_outputs,
				
				rpm_defines = {
						
						"_topdir" : self.rpm_outputs,
						# _rpmconfigdir
						
						"_specdir" : "%{_topdir}/SPECS",
						"_sourcedir" : "%{_topdir}/SOURCES",
						"_rpmdir" : "%{_topdir}/RPMS",
						"_srcrpmdir" : "%{_topdir}/SRPMS",
						"_builddir" : "%{_topdir}/BUILD",
						"_buildrootdir" : "%{_topdir}/BUILDROOT",
						
						"_tmppath" : self._temporary,
						
						"_rpmfilename" : "package.rpm",
						
						"__check_files" : _true_path,
						"__find_provides" : _true_path,
						"__find_requires" : _true_path,
						"__find_conflicts" : _true_path,
						"__find_obsoletes" : _true_path,
						
						"__spec_prep_cmd" : _true_path,
						"__spec_build_cmd" : _true_path,
						"__spec_install_cmd" : _true_path,
						"__spec_check_cmd" : _true_path,
						"__spec_clean_cmd" : _true_path,
				},
				
				# rpm_rc = "/dev/null",
				rpm_db = PathValue (None, [self.rpm_outputs, "DB"]),
				
				strace = None),
		)
		
		_commands.append (CpCommand (**self._command_arguments) .instantiate (
				self._package_archive,
				PathValue (self._context, [self.rpm_outputs, "RPMS/package.rpm"])))
		
		return SequentialCommandInstance (_commands)
	
	def _initialize (self, _descriptor) :
		self._initialize_package (_descriptor)
		self._initialize_definitions (_json_select (_descriptor, ("definitions",), dict, required = False, default = {}))
		self._initialize_resources (_json_select (_descriptor, ("resources",), dict, required = False, default = {}))
		self._initialize_overlays (_json_select (_descriptor, ("overlays",), list, required = False, default = []), self._package_outputs)
		self._initialize_dependencies (_json_select (_descriptor, ("dependencies",), dict, required = False, default = {}))
		self._initialize_rpm (_descriptor)
	
	def _initialize_package (self, _descriptor) :
		
		self.package_name = ExpandableStringValue (self._context,
				_json_select (_descriptor, ("package", "name"), basestring),
				pattern = _rpm_package_name_re, identifier = "package:name")
		self.package_version = ExpandableStringValue (self._context,
				_json_select (_descriptor, ("package", "version"), basestring),
				pattern = _rpm_package_version_re, identifier = "package:version")
		self.package_release = ExpandableStringValue (self._context,
				_json_select (_descriptor, ("package", "release"), basestring),
				pattern = _rpm_package_release_re, identifier = "package:release")
		self.package_architecture = ExpandableStringValue (self._context,
				_json_select (_descriptor, ("package", "architecture"), basestring),
				pattern = _rpm_architecture_re, identifier = "package:architecture")
		self.package_root = PathValue (self._context,
				[ExpandableStringValue (self._context,
						_json_select (_descriptor, ("package", "root"), basestring),
						pattern = _target_path_re)],
				identifier = "package:root")
		self.package_identifier = LambdaValue (self._context,
				lambda : "%s-%s" % (self.package_name (), self.package_version ()),
				identifier = "package:identifier")
	
	def _initialize_rpm (self, _descriptor) :
		
		self.rpm_license = LicenseValue (self._context,
				ExpandableStringValue (self._context,
						_json_select (_descriptor, ("miscellaneous", "license"), basestring, required = False)))
		self.rpm_summary = ExpandableStringValue (self._context,
				_json_select (_descriptor, ("miscellaneous", "summary"), basestring, required = False))
		self.rpm_url = ExpandableStringValue (self._context,
				_json_select (_descriptor, ("miscellaneous", "url"), basestring, required = False))
		
		self.rpm_outputs = PathValue (self._context, [self._temporary, "rpm-outputs"])
		self.rpm_spec = PathValue (self._context, [self._temporary, "rpm.spec"])
	
	def _initialize_dependencies (self, _descriptor) :
		self._initialize_provides (_json_select (_descriptor, ("provides",), list, required = False, default = []))
		self._initialize_requires (_json_select (_descriptor, ("requires",), list, required = False, default = []))
	
	def _initialize_provides (self, _descriptors) :
		self._rpm_provides = []
		for _index in xrange (len (_descriptors)) :
			_provided = ExpandableStringValue (self._context,
					_json_select (_descriptors, (_index,), basestring),
					pattern = _rpm_package_name_re)
			self._rpm_provides.append (_provided)
	
	def _initialize_requires (self, _descriptors) :
		self._rpm_requires = []
		for _index in xrange (len (_descriptors)) :
			_required = ExpandableStringValue (self._context,
					_json_select (_descriptors, (_index,), basestring),
					pattern = _rpm_package_name_re)
			self._rpm_requires.append (_required)
	
	def describe (self, _scroll) :
		
		_scroll.append ("composite package builder:")
		
		_scroll.append ("package:", indentation = 1)
		_subscroll = _scroll.splice (indentation = 2)
		_subscroll.appendf ("name: `%s`;", self.package_name)
		_subscroll.appendf ("version: `%s`;", self.package_version)
		_subscroll.appendf ("release: `%s`;", self.package_release)
		_subscroll.appendf ("architecture: `%s;`", self.package_architecture)
		_subscroll.appendf ("root: `%s;`", self.package_root)
		
		_scroll.append ("provides:", indentation = 2)
		_subscroll = _scroll.splice (indentation = 3)
		for _provided in self._rpm_provides :
			_subscroll.appendf ("`%s`;", _provided)
		
		_scroll.append ("requires:", indentation = 2)
		_subscroll = _scroll.splice (indentation = 3)
		for _required in self._rpm_requires :
			_subscroll.appendf ("`%s`;", _required)
		
		_subscroll = _scroll.splice (indentation = 1)
		self._describe_resources (_subscroll)
		self._describe_overlays (_subscroll)
		
		_scroll.append ("environment:", indentation = 1)
		_subscroll = _scroll.splice (indentation = 2)
		_subscroll.appendf ("sources: `%s`;", self._sources)
		_subscroll.appendf ("package archive: `%s`;", self._package_archive)
		_subscroll.appendf ("package outputs: `%s`;", self._package_outputs)
		_subscroll.appendf ("resource outputs: `%s`;", self._resource_outputs)
		_subscroll.appendf ("temporary: `%s`;", self._temporary)
		_subscroll.appendf ("timestamp: `%s`;", self._timestamp)
		self._describe_definitions (_subscroll)

_rpm_package_name_re = re.compile ("^.*$")
_rpm_package_version_re = re.compile ("^.*$")
_rpm_package_release_re = re.compile ("^.*$")
_rpm_architecture_re = re.compile ("^.*$")

_resource_uri_re = re.compile ("^.*$")

_target_path_part_pattern = "(?:[a-z0-9._-]+)"
_target_path_part_re = re.compile ("^%s$" % (_target_path_part_pattern,))
_target_path_pattern = "(?:(?:/%s)+)" % (_target_path_part_pattern,)
_target_path_re = re.compile ("^%s$" % (_target_path_pattern,))

_normal_path_part_pattern = "(?:[ -.0-~]+)"
_normal_path_part_re = re.compile ("^%s$" % (_normal_path_part_pattern,))
_normal_path_absolute_pattern = "(?:(?:/%s)+)" % (_normal_path_part_pattern,)
_normal_path_relative_pattern = "(?:(?:%s)(?:/%s)*)" % (_normal_path_part_pattern, _normal_path_part_pattern)
_normal_path_pattern = "(?:%s|%s|/)" % (_normal_path_absolute_pattern, _normal_path_relative_pattern)
_normal_path_re = re.compile ("^%s$" % (_normal_path_pattern,))


class Overlay (object) :
	
	def __init__ (self, _builder, _root, _target) :
		self._root = _root
		self._target = _target
		self._command_arguments = _builder._command_arguments
	
	def instantiate (self) :
		raise Exception ("wtf!")
	
	def describe (self, _scroll) :
		raise Exception ("wtf!")


class UnarchiverOverlay (Overlay) :
	
	def __init__ (self, _builder, _root, _target, _resource, _format) :
		Overlay.__init__ (self, _builder, _root, _target)
		self._resource = _resource
		self._format = _format
	
	def instantiate (self) :
		
		_format = _coerce (self._format, basestring)
		if _format == "cpio+gzip" :
			_archive_format = "cpio"
			_stream_format = "gzip"
		else :
			raise Exception ("wtf!")
		
		_commands = []
		
		if _stream_format == "gzip" :
			_gunzip_input, _gunzip_output = _create_pipe_values (None)
			_command = GzipExtractCommand (**self._command_arguments) .instantiate (_gunzip_output, self._resource)
			_commands.append (_command)
			_stream = _gunzip_input
			
		elif _stream_format is None :
			_stream = self._resource
			
		else :
			raise Exception ("wtf!")
		
		_target = PathValue (None, [self._root, self._target])
		
		if _archive_format == "cpio" :
			_command = CpioExtractCommand (**self._command_arguments) .instantiate (_target, _stream)
			_commands.append (_command)
		
		_commands = ParallelCommandInstance (_commands)
		
		_command = MkdirCommand (**self._command_arguments) .instantiate (_target, True)
		_commands = SequentialCommandInstance ([_command, _commands])
		
		return _commands
	
	def describe (self, _scroll) :
		_scroll.append ("unarchiver overlay:")
		_scroll.appendf ("target: `%s`;", self._target, indentation = 1)
		_scroll.appendf ("resource: `%s`;", self._resource, indentation = 1)
		_scroll.appendf ("format: `%s`;", self._format, indentation = 1)
		_scroll.appendf ("root: `%s`;", self._root, indentation = 1)


class SymlinksOverlay (Overlay) :
	
	def __init__ (self, _builder, _root, _target, _links) :
		Overlay.__init__ (self, _builder, _root, _target)
		self._links = _links
	
	def instantiate (self) :
		_commands = []
		_command = MkdirCommand (**self._command_arguments) .instantiate (PathValue (None, [self._root, self._target]), True)
		_commands.append (_command)
		for _target, _source in self._links :
			_target = PathValue (None, [self._root, self._target, _target])
			_commands.append (LnCommand (**self._command_arguments) .instantiate (_target, _source, True))
		return SequentialCommandInstance (_commands)
	
	def describe (self, _scroll) :
		_scroll.append ("symlinks overlay:")
		_scroll.appendf ("target: `%s`;", self._target, indentation = 1)
		_scroll.append ("links:", indentation = 1)
		_links = {}
		for _target, _source in self._links :
			_links[_target] = _source
		for _target in sorted (_links.keys ()) :
			_source = _links[_target]
			_scroll.appendf ("`%s` -> `%s`;", _target, _source, indentation = 2)
		_scroll.appendf ("root: `%s`;", self._root, indentation = 1)


class Resource (object) :
	
	def __init__ (self, _builder, _identifier) :
		self._identifier = _identifier
		self._command_arguments = _builder._command_arguments
	
	def instantiate (self) :
		raise Exception ("wtf!")
	
	def describe (self, _scroll) :
		raise Exception ("wtf!")


class FetcherResource (Resource) :
	
	def __init__ (self, _builder, _identifier, _uri, _output) :
		Resource.__init__ (self, _builder, _identifier)
		self._uri = _uri
		self._output = _output
		self.path = self._output
	
	def instantiate (self) :
		return SafeCurlCommand (**self._command_arguments) .instantiate (self._output, self._uri)
	
	def describe (self, _scroll) :
		_scroll.append ("fetcher resource:")
		_scroll.appendf ("identifier: `%s`;", self._identifier, indentation = 1)
		_scroll.appendf ("uri: `%s`;", self._uri, indentation = 1)
		_scroll.appendf ("output: `%s`;", self._output, indentation = 1)


class Context (object) :
	
	def __init__ (self) :
		self._values = []
		self._resolvable_values = {}
	
	def register_value (self, _identifier, _value) :
		if _context_value_identifier_re.match (_identifier) is None :
			raise Exception ("wtf!")
		if _identifier in self._resolvable_values :
			raise Exception ("wtf!")
		self._resolvable_values[_identifier] = _value
		return _value
	
	def resolve_value (self, _identifier) :
		if not _identifier in self._resolvable_values :
			raise Exception ("wtf! %s" % _identifier)
		_value = self._resolvable_values[_identifier]
		return _value

_context_value_identifier_part_pattern = "(?:[a-z0-9](?:[.-]?[a-z0-9])*)"
_context_value_identifier_pattern = "(?:%s(?::%s)*)" % (_context_value_identifier_part_pattern, _context_value_identifier_part_pattern)
_context_value_identifier_re = re.compile ("^%s$" % (_context_value_identifier_pattern,))


class ContextValue (object) :
	
	def __init__ (self, _context, identifier = None, constraints = None) :
		
		self._context = _context
		self._identifier = identifier
		self._constraints = constraints if constraints is not None and len (constraints) > 0 else None
		self._resolved = False
		self._value = None
		
		if self._identifier is not None :
			self._context.register_value (self._identifier, self)
	
	def __call__ (self) :
		if self._resolved is None :
			raise Exception ("wtf!")
		if not self._resolved :
			self._resolved = None
			_value = self._resolve ()
			if self._constraints is not None :
				for _constraint in self._constraints :
					if not _constraint (_value) :
						raise Exception ("wft! %s" % (_value,))
			self._value = _value
			self._resolved = True
		return self._value
	
	def _resolve (self) :
		raise Exception ("wtf!")
	
	def __str__ (self) :
		return repr (self)
	
	def __repr__ (self) :
		raise Exception ("wtf!")


class ConstantValue (ContextValue) :
	
	def __init__ (self, _context, _value, **_arguments) :
		ContextValue.__init__ (self, _context, **_arguments)
		self._constant = _value
	
	def _resolve (self) :
		return self._constant
	
	def __repr__ (self) :
		return repr (self._constant)


class LambdaValue (ContextValue) :
	
	def __init__ (self, _context, _lambda, **_arguments) :
		ContextValue.__init__ (self, _context, **_arguments)
		self._lambda = _lambda
	
	def _resolve (self) :
		return self._lambda ()
	
	def __repr__ (self) :
		return "<LambdaValue: %r>" % (self._lambda,)


class ExpandableStringValue (ContextValue) :
	
	def __init__ (self, _context, _template, pattern = None, constraints = [], **_arguments) :
		
		if constraints is None :
			constraints = []
		if pattern is None :
			pass
		elif isinstance (pattern, type (_expandable_string_template_re)) :
			constraints = [lambda _string : pattern.match (_string) is not None] .extend (constraints)
		elif isinstance (pattern, basestring) :
			constraints = [lambda _string : re.match (pattern, _string) is not None] .extend (constraints)
		
		ContextValue.__init__ (self, _context, constraints = constraints, **_arguments)
		self._template = _template
		self._coercer = type (self._template)
	
	def _resolve (self) :
		_match = _expandable_string_template_re.match (self._template)
		if _match is None :
			raise Exception ("wtf!")
		_value = re.sub (_expandable_string_template_variable_re, self._resolve_variable_value, self._template)
		return _value
	
	def _resolve_variable_value (self, _identifier_match) :
		_identifier = _identifier_match.group (0) [2 : -1]
		_value = self._context.resolve_value (_identifier)
		_value = _value ()
		_value = self._coercer (_value)
		return _value
	
	def __repr__ (self) :
		return self ()


_expandable_string_template_variable_pattern = "(?:@\{%s\})" % (_context_value_identifier_pattern,)
_expandable_string_template_variable_re = _expandable_string_template_variable_pattern
_expandable_string_template_pattern = "(?:(?:.*(?:%s).*)*|[^@]*)" % (_expandable_string_template_variable_pattern,)
_expandable_string_template_re = re.compile ("^%s$" % (_expandable_string_template_pattern,))


class PathValue (ContextValue) :
	
	def __init__ (self, _context, _parts, pattern = _normal_path_re, constraints = [], temporary = False, **_arguments) :
		ContextValue.__init__ (self, _context,
				constraints = [
						lambda _path : pattern.match (_path) is not None]
						.extend (constraints),
				**_arguments)
		self._parts = _parts
		self._temporary = temporary
	
	def _resolve (self) :
		_parts = [_coerce (_part, basestring) for _part in self._parts]
		for _index in xrange (len (_parts)) :
			_part = _parts[_index]
			if _part[0] == "/" and _index > 0 :
				_part = "." + _part
			_parts[_index] = _part
		_value = path.join (*_parts)
		_value = path.normpath (_value)
		if self._temporary :
			_value = _resolve_temporary_path (_value)
		return _value
	
	def __repr__ (self) :
		return self ()


class FileValue (ContextValue) :
	
	def __init__ (self, _context, _descriptor, _mode, **_arguments) :
		ContextValue.__init__ (self, _context, **_arguments)
		self._descriptor = _descriptor
		self._mode = _mode
	
	def _resolve (self) :
		_value = _coerce_file (self._descriptor, self._mode)
		return _value
	
	def __repr__ (self) :
		return "<FileValue, descriptor: %r, mode: %r>" % (self._descriptor, self._mode)


def _create_pipe_values (_context, **_arguments) :
	
	_descriptors = [None, None]
	
	def _open () :
		_logger.debug ("opening pipes...")
		_descriptors[0], _descriptors[1] = os.pipe ()
	
	def _input () :
		if _descriptors[0] is None :
			_open ()
		return _descriptors[0]
	
	def _output () :
		if _descriptors[1] is None :
			_open ()
		return _descriptors[1]
	
	return FileValue (_context, _input, "r", **_arguments), FileValue (_context, _output, "w", **_arguments)


class ResolvableValue (ContextValue) :
	
	def __init__ (self, _context, _identifier, _resolver, **_arguments) :
		ContextValue.__init__ (self, _context, **_arguments)
		self._identifier = _identifier
		self._resolver = _resolver
	
	def _resolve (self) :
		_identifier = self._identifier ()
		_value = self._resolver (_identifier)
		return (_value)
	
	def __repr__ (self) :
		return "<ResolvableValue, identifier: %r, resolver: %r>" % (self._identifier, self._resolver)


class LicenseValue (ContextValue) :
	
	def __init__ (self, _context, _identifier, constraints = [], **_arguments) :
		ContextValue.__init__ (self, _context,
				constraints = [
						lambda _identifier : _license_identifier_re.match (_identifier) is not None,
						lambda _identifier : _identifier in _license_rpm_names]
						.extend (constraints),
				**_arguments)
		self._identifier = _identifier
	
	def _resolve (self) :
		return self._identifier ()
	
	def rpm_name (self) :
		return _license_rpm_names[self ()]
	
	def __repr__ (self) :
		return self.rpm_name ()

_license_identifier_pattern = "(?:[a-z0-9]+|[a-z0-9]-(?:[0-9]+|[0-9]+\.[0-9]+))"
_license_identifier_re = re.compile ("^%s$" % (_license_identifier_pattern,))

_license_rpm_names = {
		"apache-2.0" : "Apache 2.0",
}


class Command (object) :
	
	def __init__ (self) :
		pass
	
	def execute (self, *_list_arguments, **_map_arguments) :
		_instance = self.instantiate (*_list_arguments, **_map_arguments)
		return _instance.execute (**_map_arguments)
	
	def instantiate (self, *_list_arguments, **_map_arguments) :
		raise Exception ("wtf!")


class BasicCommand (Command) :
	
	def __init__ (self, _executable, environment = {}) :
		Command.__init__ (self)
		self._executable = _resolve_executable_path (_executable)
		self._argument0 = None
		self._environment = environment
	
	def _instantiate_1 (self, _arguments, stdin = None, stdout = None, stderr = None, root = None, strace = None) :
		if strace is None :
			return ExternalCommandInstance (self._executable, self._argument0, _arguments, self._environment, stdin, stdout, stderr, root)
		else :
			_strace_executable = "strace"
			_strace_arguments = []
			_strace_arguments.extend (["-f"])
			for _strace_event in strace :
				_strace_arguments.extend (["-e", _strace_event])
			_strace_arguments.append ("--")
			_strace_arguments.append (self._executable)
			_strace_arguments.extend (_arguments)
			return ExternalCommandInstance (_strace_executable, None, _strace_arguments, self._environment, stdin, stdout, stderr, root)


class MkdirCommand (BasicCommand) :
	
	def __init__ (self, **_arguments) :
		BasicCommand.__init__ (self, "mkdir", **_arguments)
	
	def instantiate (self, _target, _recursive = False) :
		if _recursive :
			return self._instantiate_1 (["-p", "--", _target])
		else :
			return self._instantiate_1 (["--", _target])


class MvCommand (BasicCommand) :
	
	def __init__ (self, **_arguments) :
		BasicCommand.__init__ (self, "mv", **_arguments)
	
	def instantiate (self, _target, _source) :
		return self._instantiate_1 (["-T", "--", _source, _target])


class LnCommand (BasicCommand) :
	
	def __init__ (self, **_arguments) :
		BasicCommand.__init__ (self, "ln", **_arguments)
	
	def instantiate (self, _target, _source, _symbolic = True) :
		if _symbolic :
			return self._instantiate_1 (["-s", "-T", "--", _source, _target])
		else :
			return self._instantiate_1 (["-T", "--", _source, _target])


class CpCommand (BasicCommand) :
	
	def __init__ (self, **_arguments) :
		BasicCommand.__init__ (self, "cp", **_arguments)
	
	def instantiate (self, _target, _source) :
		return self._instantiate_1 (["-T", "-p", "--", _source, _target])


class RmCommand (BasicCommand) :
	
	def __init__ (self, **_arguments) :
		BasicCommand.__init__ (self, "rm", **_arguments)
	
	def instantiate (self, _target, _recursive = False) :
		if _recursive :
			return self._instantiate_1 (["-R", "--", _target])
		else :
			return self._instantiate_1 (["--", _target])


class ChmodCommand (BasicCommand) :
	
	def __init__ (self, **_arguments) :
		BasicCommand.__init__ (self, "chmod", **_arguments)
	
	def instantiate (self, _target, _mode, _recursive = False) :
		if _recursive :
			return self._instantiate_1 (["-R", _mode, "--", _target])
		else :
			return self._instantiate_1 ([_mode, "--", _target])


class ZipExtractCommand (BasicCommand) :
	
	def __init__ (self, **_arguments) :
		BasicCommand.__init__ (self, "unzip", **_arguments)
	
	def instantiate (self, _target, _archive) :
		return self._instantiate_1 (["-b", "-D", "-n", "-q", "-d", _target, "--", _archive])


class SafeZipExtractCommand (Command) :
	
	def __init__ (self, **_arguments) :
		Command.__init__ (self)
		self._mkdir = MkdirCommand (**_arguments)
		self._unzip = ZipExtractCommand (**_arguments)
		self._mv = MvCommand (**_arguments)
	
	def instantiate (self, _target, _archive) :
		_safe_target = _resolve_temporary_path (_target)
		_mkdir = self._mkdir.instantiate (_safe_target)
		_unzip = self._unzip.instantiate (_safe_target, _archive)
		_mv = self._mv.instantiate (_target, _safe_target)
		return SequentialCommandInstance ([_mkdir, _unzip, _mv])


class GzipExtractCommand (BasicCommand) :
	
	def __init__ (self, **_arguments) :
		BasicCommand.__init__ (self, "gzip", **_arguments)
	
	def instantiate (self, _target, _input) :
		return self._instantiate_1 (["-d", "-c"], stdin = _input, stdout = _target)


class CpioExtractCommand (BasicCommand) :
	
	def __init__ (self, **_arguments) :
		BasicCommand.__init__ (self, "cpio", **_arguments)
	
	def instantiate (self, _target, _input) :
		return self._instantiate_1 (
				["-i", "-H", "newc", "--make-directories", "--no-absolute-filenames", "--no-preserve-owner", "--quiet"],
				stdin = _input, root = _target)


class CurlCommand (BasicCommand) :
	
	def __init__ (self, **_arguments) :
		BasicCommand.__init__ (self, "curl", **_arguments)
	
	def instantiate (self, _target, _uri) :
		return self._instantiate_1 (["-s", "-f", "-o", _target, "--retry", "3", "--", _uri])


class SafeCurlCommand (Command) :
	
	def __init__ (self, **_arguments) :
		Command.__init__ (self)
		self._curl = CurlCommand (**_arguments)
		self._mv = MvCommand (**_arguments)
	
	def instantiate (self, _target, _uri) :
		_safe_target = PathValue (None, [_target], temporary = True)
		_curl = self._curl.instantiate (_safe_target, _uri)
		_mv = self._mv.instantiate (_target, _safe_target)
		return SequentialCommandInstance ([_curl, _mv])


class RpmBuildCommand (BasicCommand) :
	
	def __init__ (self, **_arguments) :
		BasicCommand.__init__ (self, "rpmbuild", **_arguments)
	
	def instantiate (self, _spec, rpm_macros = None, rpm_buildroot = None, rpm_buildtarget = None, rpm_defines = None, rpm_rc = None, rpm_db = None, quiet = True, debug = False, strace = None) :
		
		_arguments = []
		
		_arguments.append ("-bb")
		if quiet :
			_arguments.append ("--quiet")
		elif debug :
			_arguments.append ("-vv")
		
		if rpm_rc is not None :
			_arguments.extend (["--rcfile", rpm_rc])
		if rpm_db is not None :
			_arguments.extend (["--dbpath", rpm_db])
		
		if rpm_macros is not None :
			_arguments.extend (["--macros", rpm_macros])
		if rpm_buildroot is not None :
			_arguments.extend (["--buildroot", rpm_buildroot])
		if rpm_buildtarget is not None :
			_arguments.extend (["--target", rpm_buildtarget])
		
		if rpm_defines is not None :
			for _name, _value in rpm_defines.items () :
				def _define_lambda (_name, _value) :
					return LambdaValue (None, lambda : "%s %s" % (_coerce (_name, basestring), _coerce (_value, basestring)))
				_arguments.extend (["--define", _define_lambda (_name, _value)])
		
		_arguments.append ("--")
		_arguments.append (_spec)
		
		return self._instantiate_1 (_arguments, strace = strace)


class SequentialCommandInstance (object) :
	
	def __init__ (self, _commands) :
		self._commands = _commands
	
	def execute (self, wait = True) :
		if not wait :
			raise Exception ("wtf!")
		for _command in self._commands :
			_command.execute (wait = True)
		if wait :
			self.wait ()
	
	def wait (self) :
		for _command in self._commands :
			_command.wait ()
	
	def describe (self, _scroll) :
		_scroll.append ("sequential commands:")
		_subscroll = _scroll.splice (indentation = 1)
		for _command in self._commands :
			_command.describe (_subscroll)


class ParallelCommandInstance (object) :
	
	def __init__ (self, _commands) :
		self._commands = _commands
	
	def execute (self, wait = True) :
		for _command in self._commands :
			_command.execute (wait = False)
		if wait :
			self.wait ()
	
	def wait (self) :
		for _command in self._commands :
			_command.wait ()
	
	def describe (self, _scroll) :
		_scroll.append ("parallel commands:")
		_subscroll = _scroll.splice (indentation = 1)
		for _command in self._commands :
			_command.describe (_subscroll)


class ExternalCommandInstance (object) :
	
	def __init__ (self, _executable, _argument0, _arguments, _environment, _stdin, _stdout, _stderr, _root) :
		self._executable = _executable
		self._argument0 = _argument0 or path.basename (self._executable)
		self._arguments = _arguments or []
		self._environment = _environment or os.environ
		self._stdin = _stdin
		self._stdout = _stdout
		self._stderr = _stderr
		self._root = _root or os.environ.get ("TMPDIR") or "/tmp"
		self._process = None
	
	def execute (self, wait = True) :
		
		if self._process is not None :
			raise Exception ()
		
		_executable = _coerce (self._executable, basestring)
		_argument0 = _coerce (self._argument0, basestring)
		_arguments = [_coerce (_argument, basestring) for _argument in self._arguments]
		_environment = {_coerce (_name, basestring) : _coerce (_value, basestring) for _name, _value in self._environment.items ()}
		_stdin = _coerce_file (self._stdin, "r", True)
		_stdout = _coerce_file (self._stdout, "w", True)
		_stderr = _coerce_file (self._stderr, "w", True)
		_root = _coerce (self._root, basestring)
		
		if _stdin is not None :
			_stdin_1 = None
		else :
			_stdin_1, _stdin_2 = os.pipe ()
			os.close (_stdin_2)
			_stdin = _stdin_1
		if _stdout is not None :
			_stdout_1 = None
		else :
			_stdout_2, _stdout_1 = os.pipe ()
			os.close (_stdout_2)
			_stdout = _stdout_1
		if _stderr is not None :
			pass
		else :
			_stderr = sys.stderr
		
		_stdin = _coerce_file (_stdin, "r")
		_stdout = _coerce_file (_stdout, "w")
		_stderr = _coerce_file (_stderr, "w")
		
		_logger.debug ("executing `%s %s`...", _argument0, " ".join (_arguments))
		
		self._process = subprocess.Popen (
				[_argument0] + _arguments,
				executable = _executable,
				stdin = _stdin,
				stdout = _stdout,
				stderr = _stderr,
				close_fds = True,
				cwd = _root,
				env = _environment)
		
		if _stdin_1 is not None :
			_stdin.close ()
		if _stdout_1 is not None :
			_stdout.close ()
		
		if wait :
			self.wait ()
	
	def wait (self) :
		
		_outcome = self._process.wait ()
		
		if _outcome != 0 :
			raise Exception (_outcome)
	
	def describe (self, _scroll) :
		_scroll.append ("external command:")
		_scroll.appendf ("executable: `%s`;", self._executable, indentation = 1)
		_scroll.appendf ("argument0: `%s`;", self._argument0, indentation = 1)
		_scroll.appendf ("arguments: `%s`;", lambda : "`, `".join ([str (_argument) for _argument in self._arguments]), indentation = 1)
		_scroll.appendf ("stdin: `%s`;", self._stdin, indentation = 1)
		_scroll.appendf ("stdout: `%s`;", self._stdout, indentation = 1)
		_scroll.appendf ("stderr: `%s`;", self._stderr, indentation = 1)
		_scroll.appendf ("root: `%s`;", self._root, indentation = 1)


class FileCreateCommand (Command) :
	
	def __init__ (self, **_arguments) :
		Command.__init__ (self)
	
	def instantiate (self, _target, _chunks) :
		return FileCreateCommandInstance (_target, _chunks)


class FileCreateCommandInstance (object) :
	
	def __init__ (self, _target, _chunks) :
		self._target = _target
		self._chunks = _chunks
	
	def execute (self, wait = True) :
		_chunks = _coerce (self._chunks, None)
		with _coerce_file (self._target, "w") as _stream :
			for _chunk in _chunks :
				_stream.write (_chunk)
	
	def wait (self) :
		pass
	
	def describe (self, _scroll) :
		_scroll.append ("file create command:")
		_scroll.appendf ("target: `%s`;", self._target, indentation = 1)
		_scroll.appendf ("chunks: `%s`;", self._chunks, indentation = 1)


class SafeFileCreateCommand (Command) :
	
	def __init__ (self, **_arguments) :
		Command.__init__ (self)
		self._create = FileCreateCommand (**_arguments)
		self._mv = MvCommand (**_arguments)
	
	def instantiate (self, _target, _chunks) :
		_safe_target = PathValue (None, [_target], temporary = True)
		_create = self._create.instantiate (_safe_target, _chunks)
		_mv = self._mv.instantiate (_target, _safe_target)
		return SequentialCommandInstance ([_create, _mv])


class Scroll (object) :
	
	def __init__ (self) :
		self._blocks = []
	
	def append (self, _string, **_modifiers) :
		self.include_lines ([_string], **_modifiers)
	
	def appendf (self, _format, *_parts, **_modifiers) :
		_line = [_format]
		_line.extend (_parts)
		_line = tuple (_line)
		self.include_lines ([_line], **_modifiers)
	
	def include_lines (self, _lines, priority = 0, indentation = 0) :
		_block = (_lines, priority, indentation)
		self._blocks.append (_block)
	
	def include_scroll (self, _scroll, priority = 0, indentation = 0) :
		_block = (_scroll, priority, indentation)
		self._blocks.append (_block)
	
	def splice (self, **_modifiers) :
		_scroll = Scroll ()
		self.include_scroll (_scroll, **_modifiers)
		return _scroll
	
	def lines (self) :
		for _line, _indentation in self._lines () :
			_line = self._format (_line, _indentation)
			yield _line
	
	def lines_with_nl (self) :
		for _line in self.lines () :
			_line = _line + "\n"
			yield _line
	
	def _lines (self) :
		
		_blocks = sorted (self._blocks, lambda _left, _right : _left[1] < _right[1])
		
		for _lines, _priority, _indentation in _blocks :
			
			if isinstance (_lines, Scroll) :
				for _line, _indentation_1 in _lines._lines () :
					yield _line, _indentation + _indentation_1
				
			elif isinstance (_lines, list) :
				for _line in _lines :
					if isinstance (_line, basestring) or isinstance (_line, tuple) :
						yield _line, _indentation
					else :
						raise Exception ("wtf!")
				
			else :
				raise Exception ("wtf!")
	
	def _format (self, _line, _indentation) :
		
		if isinstance (_line, basestring) :
			pass
			
		elif isinstance (_line, tuple) :
			_format = _line[0]
			_parts = tuple ([_coerce (_part, (basestring, int, long, float, complex, ContextValue), True) for _part in _line[1:]])
			_line = _format % _parts
			
		else :
			raise Exception ("wtf!")
		
		_line = ("\t" * _indentation) + _line
		
		return _line
	
	def output (self, _stream) :
		for _line in self.lines_with_nl () :
			_stream.write (_line)
		_stream.flush ()
	
	def stream (self, _stream) :
		for _line in self.lines () :
			_stream (_line)



def _mkdirs (_path) :
	if path.isdir (_path) :
		return
	if path.exists (_path) :
		raise Exception ("wtf!")
	_logger.debug ("creating folder `%s`...", _path)
	os.makedirs (_path)


def _json_load (_path) :
	_logger.debug ("loading JSON from `%s`...", _path)
	with open (_path, "r") as _stream :
		return json.load (_stream)

def _json_select (_root, _keys, _type, required = True, default = None) :
	for _key in _keys :
		if isinstance (_key, basestring) :
			if not isinstance (_root, dict) :
				raise Exception ("wtf!")
			elif _key in _root :
				_root = _root[_key]
			elif required :
				raise Exception ("wtf!")
			else :
				_root = default
				break
		elif isinstance (_key, int) :
			if not isinstance (_root, list) :
				raise Exception ("wft!")
			else :
				_root = _root[_key]
		else :
			raise Exception ("wtf!")
	if not isinstance (_root, _type) :
		raise Exception ("wft!")
	return _root


def _resolve_executable_path (_name) :
	# FIXME: !!!
	return ("/bin/" + _name)


def _resolve_temporary_path (_target) :
	return "%s/.tmp--%s--%s" % (path.dirname (_target), path.basename (_target), _create_token ())


def _create_token () :
	return uuid.uuid4 () .hex


def _coerce (_object, _type, _none_allowed = False) :
	while True :
		if _object is None and _none_allowed :
			break
		if _type is not None:
			if isinstance (_type, type) :
				if isinstance (_object, _type) :
					break
			elif isinstance (_type, tuple) :
				_ok = False
				for _type_1 in _type :
					if isinstance (_object, _type_1) :
						_ok = True
						break
				if _ok :
					break
			else :
				raise Exception ("wtf!")
		if callable (_object) :
			_object = _object ()
			continue
		if _type is None :
			break
		raise Exception ("wft! %s %s" % (_object, _type))
	return _object


def _coerce_file (_object, _mode, _none_allowed = False) :
	_object = _coerce (_object, (file, basestring, int), _none_allowed)
	if _object is None and _none_allowed :
		_file = None
	elif isinstance (_object, basestring) :
		_logger.debug ("opening file `%s` with mode `%s`...", _object, _mode)
		_file = open (_object, _mode)
	elif isinstance (_object, int) :
		_file = os.fdopen (_object, _mode)
	elif isinstance (_object, file) :
		_file = _object
	else :
		raise Exception ("wtf!")
	return _file


import logging
logging.basicConfig ()
_logger = logging.getLogger ("mosaic-mpb")
_logger.setLevel (logging.DEBUG)


if __name__ == "__wrapped__" :
	
	_main (__configuration__)
	
	__exit__ (0)
	
elif __name__ == "__main__" :
	
	_configuration = {
			
			"descriptor" : None,
			"sources" : None,
			"package" : None,
			"temporary" : None,
			
			"package-name" : None,
			"package-version" : None,
			"package-release" : None,
			"package-distribution" : None,
	}
	
	if len (sys.argv) == 2 :
		_workbench = sys.argv[1]
	elif len (sys.argv) == 3 :
		_workbench = sys.argv[1]
		_configuration["descriptor"] = sys.argv[2]
	else :
		raise Exception ("wtf!")
	
	_configuration["sources"] = path.join (_workbench, "sources.zip")
	_configuration["package"] = path.join (_workbench, "package.rpm")
	
	_main (_configuration)
	
	sys.exit (0)
	
else :
	raise Exception ("expected-wrapped")
