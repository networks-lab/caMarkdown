import pathlib
import os
import os.path
import fnmatch
import collections
import shutil
import re

import yaml

from .defaultFiles.defaultCodebook import makeCodeBook, codeBookName, codebookHeaders, charHeaderMap, codebookFileHeader, headerCharMap
from .defaultFiles.defaultConf import makeConf, confName
from .defaultFiles.defaultGitignore import makeGitignore, gitignoreName
from .defaultFiles.defaultCaignore import makeCAignore, caIgnoreName
from .gitWrapper import openRepo, init
from .codes import parseTree, codeTypes, makeCode
from .caExceptions import AddingException, UninitializedDirectory, ProjectDirectoryMissing, ProjectMissingFiles, ProjectException, ProjectTypeError, CodeBookException, ProjectFileError, ProjectCodeError, ProjectGitError, ProjectReservedFileError, GitRepositoryMissing

reservedFileNames = [codeBookName, confName, gitignoreName, caIgnoreName]

class Project(object):
    def __init__(self, dirName):
        if isinstance(dirName, pathlib.Path):
            self.path = dirName.resolve()
        elif isinstance(dirName, str):
            self.path = pathlib.Path(os.path.expanduser(os.path.expandvars(dirName))).resolve()
        else:
            raise ProjectTypeError("Objects of type: '{}' are not a valid input for inilizing a project object, the provided object was: {}".format(type(dirName), dirName))
        self.Repo = None
        self.error = None
        self.bad = False

        self._code = None

        try:
            self.openDir()
        except ProjectException as e:
            self.error = e
            self.bad = True

    def _openCAIgnore(self, mode = 'r'):
        try:
            f = open(str(pathlib.Path(self.path, pathlib.Path(caIgnoreName))), mode = mode)
        except FileNotFoundError:
            raise ProjectMissingFiles("{} missing".format(caIgnoreName))
        else:
            return f

    def _openGitIgnore(self, mode = 'r'):
        try:
            f = open(str(pathlib.Path(self.path, pathlib.Path(gitignoreName))), mode = mode)
        except FileNotFoundError:
            raise ProjectMissingFiles("{} missing".format(gitignoreName))
        else:
            return f

    def _openCodebook(self, mode = 'r'):
        try:
            f = open(str(pathlib.Path(self.path, pathlib.Path(codeBookName))), mode = mode)
        except FileNotFoundError:
            raise ProjectMissingFiles("{} missing".format(codeBookName))
        else:
            return f

    def openDir(self):
        try:
            self.Repo = openRepo(self.path)
        except GitRepositoryMissing:
            raise ProjectMissingFiles("{} is not a git repo. It cannot be reopen as a caMarkdown repo".format(str(self.path)))
        for name in [confName, codeBookName, gitignoreName, caIgnoreName]:
            if not pathlib.Path(self.path, name).exists():
                raise ProjectMissingFiles("{} is missing, this is not a caMarkdown repo.".format(name))

    def initializeDir(self):
        try:
            self.path.mkdir(parents = True)
        except FileExistsError:
            pass
        #Create all the missing files and directories
        try:
            self.Repo = openRepo(self.path)
        except GitRepositoryMissing:
            self.Repo = init(self.path)
        try:
            makeCodeBook(self.path)
        except FileExistsError:
            pass
        try:
            makeConf(self.path)
        except FileExistsError:
            pass
        try:
            makeGitignore(self.path)
        except FileExistsError:
            pass
        try:
            makeCAignore(self.path)
        except FileExistsError:
            pass

    def delete(self, force = False):
        """Deletes all files created by caMarkdown in the repo, including .git"""
        try:
            shutil.rmtree(str(pathlib.Path(self.path, '.git')))
        except FileNotFoundError:
            if force:
                pass
            else:
                raise ProjectFileError("The .git directory could not be found this is likely not a caMarkdown directory. If you want to retry and ignore all missing files run with `force = True`")
        try:
            os.remove(str(pathlib.Path(self.path, pathlib.Path(codeBookName))))
        except FileNotFoundError:
            if force:
                pass
            else:
                raise ProjectFileError("The codebook file could not be found this is possibly not a caMarkdown directory. If you want to retry and ignore all missing files run with `force = True`")
        try:
            os.remove(str(pathlib.Path(self.path, pathlib.Path(gitignoreName))))
        except FileNotFoundError:
            if force:
                pass
            else:
                raise ProjectFileError("The git ignore file could not be found this is possibly not a caMarkdown directory. If you want to retry and ignore all missing files run with `force = True`")
        try:
            os.remove(str(pathlib.Path(self.path, pathlib.Path(caIgnoreName))))
        except FileNotFoundError:
            if force:
                pass
            else:
                raise ProjectFileError("The ca ignore file could not be found this is possibly not a caMarkdown directory. If you want to retry and ignore all missing files run with `force = True`")
        try:
            os.remove(str(pathlib.Path(self.path, pathlib.Path(confName))))
        except FileNotFoundError:
            if force:
                pass
            else:
                raise ProjectFileError("The ca ignore file could not be found this is possibly not a caMarkdown directory. If you want to retry and ignore all missing files run with `force = True`")

    def getGitIgnoreRules(self):
        """Does not work quite right
        """
        f = self._openGitIgnore()
        rules = []
        for ruleString in (rule.split('#')[0].rstrip() for rule in f.readlines()):
            if len(ruleString) > 0:
                rules.append(lambda s: not fnmatch.fnmatch(s, ruleString))
        f.close()
        return rules

    def getCAIgnoreRules(self):
        """Does not work quite right
        """
        f = self._openCAIgnore
        rules = []
        for ruleString in (rule.split('#')[0].rstrip() for rule in f.readlines()):
            if len(ruleString) > 0:
                rules.append(lambda s: not fnmatch.fnmatch(s, ruleString))
        f.close()
        return rules

    def addDir(self, targetPath, recursive = False):
        """Adds all files in targetPath to the codebook. Each is added separately with `addFile()`. recursive will cause all subdirectories to be added as well"""
        if not isinstance(targetPath, pathlib.Path):
            targetPath = pathlib.Path(targetPath)
        try:
            targetPath = targetPath.resolve()
        except FileNotFoundError:
            raise ProjectFileError("'{}' does not exist so cannot be added.".format(targetPath))
        if not targetPath.is_dir():
            raise ProjectFileError("'{}' must be a directory.".format(targetPath))
        if self.path != targetPath and self.path not in targetPath.parents:
            raise ProjectFileError("'{}' is not in the targeted repository '{}'.".format(targetPath, self.path))
        if targetPath.name == '.git' or len([p for p in targetPath.parents if p.name == '.git']) > 0:
            raise ProjectGitError("You cannot add files from a .git directory to the codebook.")
        files = []
        subDirs = []
        for subPath in targetPath.iterdir():
            if subPath.is_dir():
                subDirs.append(subPath)
            elif subPath.is_file():
                files.append(subPath)
            #This will only catch files and directories
            #other things in the file system will be ignored.
            #It may be worth causing an error if those are found
            #but this ways seems more user friendly.
        for subFile in files:
            try:
                self.addFile(subFile)
            except ProjectReservedFileError:
                pass
        if recursive:
            for subDir in subDirs:
                try:
                    self.addDir(subDir, recursive = recursive)
                except ProjectGitError:
                    pass

    def addFile(self, targetPath):
        """Appends the codebook with the path to targetPath"""
        if not isinstance(targetPath, pathlib.Path):
            targetPath = pathlib.Path(targetPath)
        try:
            targetPath = targetPath.resolve()
        except FileNotFoundError:
            raise ProjectFileError("'{}' is not an existing file.".format(targetPath))
        if self.path not in targetPath.parents:
            raise ProjectFileError("'{}' is not in the targeted repository '{}'.".format(targetPath, self.path))
        if not targetPath.is_file():
            raise ProjectFileError("'{}' is not a file.".format(targetPath, self.path))
        if targetPath.name in reservedFileNames:
            raise ProjectReservedFileError("You cannot add a file called {} as it is a reserved name. The reserved names are: {}".format(targetPath.name,', '.join([codeBookName, confName, gitignoreName, caIgnoreName])))
        if targetPath not in self.readFilesList():
            with self._openCodebook(mode = 'r+') as f:
                yamlDict = yaml.safe_load(f)
                try:
                    yamlDict[codebookFileHeader].append(str(targetPath.relative_to(self.path)))
                except AttributeError:
                    if yamlDict[codebookFileHeader] is None:
                        yamlDict[codebookFileHeader] = [str(targetPath.relative_to(self.path))]
                    else:
                        try:
                            yamlDict[codebookFileHeader] = [{k : v} for k, v in yamlDict[codebookFileHeader].items()]
                            yamlDict[codebookFileHeader].append(str(targetPath.relative_to(self.path)))
                        except AttributeError:
                            raise
                f.seek(0)
                f.write(yaml.safe_dump(yamlDict, allow_unicode=True, default_flow_style=False))
                f.truncate()

    def addCode(self, targetCode, description = None):
        if targetCode in self.codes:
            if not self.codes[targetCode].unDocumented:
                raise ProjectCodeError("The code '{}' already exists".format(targetCode))
        if targetCode[0] not in codeTypes:
            raise ProjectCodeError("The code '{}' does not start with the correct character, it cannot be a code.".format(targetCode))
        for char in targetCode:
            if char.isspace():
                raise ProjectCodeError("The code '{}' has a whitespace character, it cannot be a code.".format(targetCode))
        if description and '\n' in description:
            raise ProjectCodeError("The description '{}' has a newline character, it must only be one line long.".format(description))
        with self._openCodebook(mode = 'r+') as f:
            yamlDict = yaml.safe_load(f)
            heading = charHeaderMap[targetCode[0]]
            try:
                yamlDict[heading].append({targetCode[1:] : {"description" : description}})
            except AttributeError:
                if yamlDict[heading] is None:
                    yamlDict[heading] = [{targetCode[1:] : {"description" : description}}]
                else:
                    try:
                        yamlDict[heading] = [{k : v} for k, v in yamlDict[heading].items()]
                        yamlDict[heading] = [{targetCode[1:] : {"description" : description}}]
                    except AttributeError:
                        raise
            f.seek(0)
            f.write(yaml.safe_dump(yamlDict, allow_unicode=True, default_flow_style=False))
            f.truncate()

    def organizeCodebook(self):
        """Rewrites the codebook with properly formatted YAML"""
        with self._openCodebook(mode = 'r+') as f:
            yamlDict = yaml.safe_load(f)
            for header in yamlDict:
                if header not in codebookHeaders:
                    raise CodeBookException("The section '{}' is no known to caMarkdown, it must be removed from the codebook.".format(header))
            for header in codebookHeaders:
                if header not in yamlDict:
                    yamlDict[header] = None
            dumpString = yaml.safe_dump(yamlDict, allow_unicode=True, default_flow_style=False)
            f.seek(0)
            f.write(re.sub(r': null\n', lambda x: '\n', dumpString))
            f.truncate()

    def getFiles(self):
        """gets all files from codebook"""
        retPaths =[]
        for fpath in self.readFilesList():
            if fpath.exists():
                retPaths.append(fpath)
        return retPaths

    def getAllTrackedFiles(self):
        """Doesn't actually read the gitignore yet
        Just gets all the files in the project dir, excluding the special ones"""
        rules = self.getGitIgnoreRules()
        def condenseRules(target, ruleLst):
            for rule in ruleLst:
                if rule(str(target)):
                    return True
            return False
        condensedRule = lambda x: condenseRules(x, rules)
        def getFiles(Path, rule):
            retLst = []
            for subPath in (p for p in Path.iterdir() if rule(p)):
                if subPath.is_dir():
                    retLst += getFiles(subPath, rule)
                else:
                    retLst.append(subPath)
            return retLst
        #TODO: Make work
        #return getFiles(self.path, condensedRule)
        return getFiles(self.path, lambda x: x.name[0] != '.' and x.name not in reservedFileNames) #Return all nonhidden files

    def parseTree(self):
        files = self.getFiles()
        if len(files) > 0:
            with open(str(files[0]), 'r') as f:
                tree = parseTree(f.read(), files[0].relative_to(self.path))
            for fname in files[1:]:
                with open(str(fname), 'r') as f:
                    tree += parseTree(f.read(), fname.relative_to(self.path))
        else:
            tree = parseTree('')
        return tree

    def readCodebook(self):
        f = self._openCodebook()
        #Maybe make load_all if header is added
        codeTree = yaml.safe_load(f)
        for header in codeTree:
            if header not in codebookHeaders:
                raise CodeBookException("A header named '{}' was found in the codebook. The only allowd headers are: {} and {}".format(header, ', '.join(codebookHeaders[:-1]), codebookHeaders[-1]))
        files = []
        codes = {}
        try:
            for filePath in codeTree[codebookFileHeader]:
                if isinstance(filePath, str):
                    files.append(pathlib.Path(self.path, filePath))
                elif isinstance(filePath, dict):
                    files.append(pathlib.Path(self.path, filePath.popitem()[0]))
                else:
                    raise CodeBookException("The files section can only contain a list of strings and dictionaries")
        except TypeError:
            if codeTree[codebookFileHeader] is None:
                pass
            else:
                raise
        for codeType, codeChar in headerCharMap.items():
            try:
                for code in codeTree[codeType]:
                    if isinstance(code, str):
                        codes[codeChar + code] = ''
                    elif isinstance(code, dict):
                        codeString, data = code.popitem()
                        if len(code) > 0:
                            raise CodeBookException("Code mappings can only contain one code. The following mapping was encountered in the mapping for {}:\n{}".format(codeString, code))
                        if isinstance(data, dict):
                            codes[codeChar + codeString] = data
                        elif isinstance(data, str):
                            codes[codeChar + codeString] = {'description' : data}
                        elif isinstance(data, list):
                            codes[codeChar + codeString] = {'description' : ' '.join(data)}
                        elif data is None:
                            codes[codeChar + codeString] = {'description' : None}
                        else:
                            raise CodeBookException("Unexpected data from the codebook entry for {}. The entry is:\n{}".format(codeChar + codeString, data))
                    else:
                        raise CodeBookException("The codes section can only contain a list of strings and dictionaries")
            except TypeError:
                if codeTree[codeType] is None:
                    pass
                else:
                    raise
        f.close()
        return codes, files

    def readCodes(self):
        return self.readCodebook()[0]

    def readFilesList(self):
        return self.readCodebook()[1]

    @property
    def codes(self):
        if self._code is None:
            self._code = self.getCodes()
        return self._code

    def getCodes(self):
        codebookCodes = self.readCodes()
        documentCodes = self.parseTree().tags
        for codeString, data in codebookCodes.items():
            if codeString in documentCodes:
                documentCodes[codeString].addDocs(data)
            else:
                unUsedCode = makeCode(codeString, dataDict = data)
                unUsedCode.unDocumented = False
                documentCodes[codeString] = unUsedCode
        return documentCodes
