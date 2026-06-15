import os, re, uuid, sys

ident = os.environ.get('SIGNING_IDENTITY', '')
spec = os.environ.get('PROFILE_SPECIFIER', '')

with open('ios/App/App.xcodeproj/project.pbxproj', 'r') as f:
    content = f.read()

# Manual signing
old = 'CODE_SIGN_STYLE = Automatic;'
new = ('CODE_SIGN_STYLE = Manual;\n'
       '\t\t\t\tCODE_SIGN_IDENTITY = "' + ident + '";\n'
       '\t\t\t\tPROVISIONING_PROFILE_SPECIFIER = "' + spec + '";')
content = content.replace(old, new)

# Build number
build_num = os.environ.get('BUILD_NUMBER', '')
if build_num:
    content = re.sub(r'CURRENT_PROJECT_VERSION = \d+;',
                     f'CURRENT_PROJECT_VERSION = {build_num};', content)

# Add PreInitICU.m to PBXSourcesBuildPhase
icu_file = 'PreInitICU.m'
if icu_file not in content:
    file_ref_id = uuid.uuid4().hex[:24].upper()
    build_file_id = uuid.uuid4().hex[:24].upper()

    file_ref = ('\t\t{0} /* PreInitICU.m */ = {{isa = PBXFileReference; '
                'fileEncoding = 4; lastKnownFileType = sourcecode.c.objc; '
                'path = "App/PreInitICU.m"; sourceTree = SOURCE_ROOT; }};\n').format(file_ref_id)
    content = content.replace('/* End PBXFileReference section */',
                              file_ref + '/* End PBXFileReference section */')

    build_file = ('\t\t{0} /* PreInitICU.m in Sources */ = {{isa = PBXBuildFile; '
                  'fileRef = {1} /* PreInitICU.m */; }};\n').format(build_file_id, file_ref_id)
    content = content.replace('/* End PBXBuildFile section */',
                              build_file + '/* End PBXBuildFile section */')

    src_phase = re.search(
        r'/\* Begin PBXSourcesBuildPhase section \*/.*?/\* End PBXSourcesBuildPhase section \*/',
        content, re.DOTALL)
    if not src_phase:
        print('ERROR: PBXSourcesBuildPhase section not found')
        sys.exit(1)
    files_open = re.search(r'(files\s*=\s*\()', src_phase.group())
    if not files_open:
        print('ERROR: files = ( not found inside PBXSourcesBuildPhase')
        sys.exit(1)
    pos = src_phase.start() + files_open.end()
    content = (content[:pos] +
               '\n\t\t\t\t{0} /* PreInitICU.m in Sources */,'.format(build_file_id) +
               content[pos:])

with open('ios/App/App.xcodeproj/project.pbxproj', 'w') as f:
    f.write(content)

print('pbxproj patched OK')
