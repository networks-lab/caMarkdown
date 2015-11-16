from .defaultFiles.defaultCodebook import makeCodeBook, codeBookName
from .defaultFiles.defaultConf import makeConf, confName
from .defaultFiles.defaultGitignore import makeGitignore, gitignoreName
from .defaultFiles.defaultCaignore import makeCAignore, caIgnoreName

from .codes import parseTree, codeTypes
from .caExceptions import AddingException, UninitializedDirectory, ProjectDirectoryMissing, ProjectMissingFiles, ProjectException, CodeBookException

import dulwich.repo
import dulwich.errors

import pathlib
import os.path
import fnmatch
import re

class Project(object):
    def __init__(self, dirName):
        self.path = pathlib.Path(os.path.expanduser(os.path.expandvars(dirName))).resolve()
        self.Repo = None
        self.error = None
        self.bad = False
        try:
            self.openDir()
        except ProjectException as e:
            self.error = e
            self.bad = True

    def openDir(self):
        try:
            os.chdir(str(self.path))
        except OSError:
            raise ProjectDirectoryMissing("{} could not be accessed, does it exist and do you have permission to acccess it?".format(self.path))
        try:
            self.Repo = dulwich.repo.Repo('.')
        except dulwich.errors.NotGitRepository:
            raise ProjectMissingFiles("{} is not a git repo. It cannot be reopen as a caMarkdown repo".format(str(self.path)))
        for name in [confName, codeBookName, gitignoreName, caIgnoreName]:
            if not pathlib.Path(name).exists():
                raise ProjectMissingFiles("{} is missing, this is not a caMarkdown repo.".format(name))

    def initializeDir(self):
        try:
            self.path.mkdir(parents = True)
        except FileExistsError:
            pass
        try:
            os.chdir(str(self.path))
        except OSError:
            raise ProjectDirectoryMissing("{} could not be accessed, do you have permission to acccess it?".format(str(self.path)))
        #Create all the missing files and directories
        try:
            self.Repo = dulwich.repo.Repo('.')
        except dulwich.errors.NotGitRepository:
            self.Repo = dulwich.repo.Repo.init('.')
        try:
            makeCodeBook()
        except FileExistsError:
            pass
        try:
            makeConf()
        except FileExistsError:
            pass
        try:
            makeGitignore()
        except FileExistsError:
            pass
        try:
            makeCAignore()
        except FileExistsError:
            pass

    def getGitIgnoreRules(self):
        """Does not work quite right
        """
        try:
            f = open(str(pathlib.Path(self.path, pathlib.Path(gitignoreName))))
        except FileNotFoundError:
            raise ProjectMissingFiles("{} missing".format(gitignoreName))
        rules = []
        for ruleString in (rule.split('#')[0].rstrip() for rule in f.readlines()):
            if len(ruleString) > 0:
                rules.append(lambda s: not fnmatch.fnmatch(s, ruleString))
        f.close()
        return rules

    def getCAIgnoreRules(self):
        """Does not work quite right
        """
        try:
            f = open(str(pathlib.Path(self.path, pathlib.Path(caIgnoreName))))
        except FileNotFoundError:
            raise ProjectMissingFiles("{} missing".format(caIgnoreName))
        rules = []
        for ruleString in (rule.split('#')[0].rstrip() for rule in f.readlines()):
            if len(ruleString) > 0:
                rules.append(lambda s: not fnmatch.fnmatch(s, ruleString))
        f.close()
        return rules

    def getFiles(self):
        rules = self.getGitIgnoreRules()
        rules += self.getCAIgnoreRules()
        def condenseRules(target, ruleLst):
            for rule in ruleLst:
                if rule(str(target)):
                    return True
            return False
        condensedRule = lambda x: condenseRules(x, ruleLst)
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
        return getFiles(self.path, lambda x: x.name[0] != '.' and x.name != 'configuration.py' and x.name != "codebook.md") #Return all nonhidden files

    def parseTree(self):
        files = self.getFiles()
        if len(files) > 0:
            with open(str(files[0]), 'r') as f:
                tree = parseTree(f.read())
            for fname in files[1:]:
                with open(str(fname), 'r') as f:
                    tree += parseTree(f.read())
        else:
            tree = parseTree('')
        return tree

    def readCodes(self):
        try:
            f = open(str(pathlib.Path(codeBookName)))
        except FileNotFoundError:
            raise ProjectMissingFiles("{} missing".format(codeBookName))
        codes = {}
        #The tag type [] cannot start with ^ as that results in negation, thus they need to be sorted before the regex sees them
        codeRegex = re.compile(r'^\s*([{}][^:\s]*)((\s*:\s*)(.*))?'.format(''.join(sorted(codeTypes.keys()))))
        for lineNum, line in enumerate(f.readlines()):
            decommentedLine = line[:-1].split('#')[0]
            if len(decommentedLine) > 0:
                regResult = re.match(codeRegex, decommentedLine)
                if regResult:
                    codes[regResult.group(1)] = regResult.group(4)
                else:
                    raise CodeBookException("Line number {0} of the codebook in {1} does not contain a code or a comment. The line is:\n{2}".format(lineNum + 1, self.path, line[:-1]))
        f.close()
        return codes
