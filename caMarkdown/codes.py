import copy

from .caExceptions import CodeParserException

contextChar = '@'
contentChar = '$'
metaChar = '^'

def lineAndIndexCounter(targtString):
    sIter = enumerate(targtString.__iter__())
    lineCount = 1
    while True:
        i, char = next(sIter)
        if char == '\n':
            lineCount += 1
        yield lineCount, i, char

class parseTree(object):
    def __init__(self, targetString, targetPath = None):
        if targetPath is not None:
            self.files = [targetPath]
        else:
            self.files = []
        sIter = lineAndIndexCounter(targetString)
        self.topNode = Node(sIter, 0, -1, '', targetPath)
        self.tagSegments = self.topNode.tagSections
        tmpTagDict = {}
        for seg in self.tagSegments:
            try:
                tmpTagDict[seg.tag].append(seg)
            except KeyError:
                tmpTagDict[seg.tag] = [seg]
        self._tags = None

    def getTags(self):
        if self._tags is None:
            tmpTagDict = {}
            for seg in self.tagSegments:
                try:
                    tmpTagDict[seg.tag].append(seg)
                except KeyError:
                    tmpTagDict[seg.tag] = [seg]
            self._tags = {tag : makeCode(tag, sections = segs) for tag, segs in tmpTagDict.items()}
        return self._tags

    def setTags(self, value):
        self._tags = value

    def delTags(self):
        del self._tags

    tags = property(getTags, setTags, delTags, "The tags of the tree")

    def __iadd__(self, other):
        self.topNode += other.topNode
        newTags = {}
        for tagString, tagObj in self.tags.items():
            if tagString in other.tags:
                newTags[tagString] = tagObj + other.tags[tagString]
            else:
                newTags[tagString] = tagObj
        for tagString, tagObj in ((s, t) for s, t in other.tags.items() if s not in newTags):
            newTags[tagString] = tagObj
        self.tags = newTags
        self.files += other.files
        return self

class Node(object):
    def __init__(self, sIter, startLine, startIndex, startCode, filePath):
        if startCode == '[':
            self.code = True
            self._raw = ''
        else:
            self.code = False
            self._raw = startCode
        self.tokens = None
        self.contents = [] #Nice values
        self._contents = [] #Raw values
        self.line = startLine
        self.index = startIndex
        self.file = filePath

        self._children = None
        self._containedSections = None
        self._tagSections = None
        self._codes = None

        stopIter = False
        inBraces = False
        currentString = ''
        currentIndex = 0
        currentLine = 1
        freshString = True

        while not stopIter:
            try:
                line, i, char = next(sIter)
                if not inBraces:
                    self._raw += char
                if freshString:
                    currentLine, currentIndex, currentString = line, i, ''
                    freshString = False
            except StopIteration:
                if inBraces:
                    currentString += '](' + self.tokens
                self._contents.append((currentLine, currentIndex, currentString))
                self.code = False
                stopIter = True
            else:
                if inBraces:
                    if char == ')':
                        stopIter = True
                    else:
                        self.tokens += char
                elif char == '[':
                    self._contents.append((currentLine, currentIndex, currentString))
                    self._raw = self._raw[:-1]
                    innerCode = Node(sIter, line, i, char, self.file)
                    self._raw += innerCode.raw
                    self._contents.append(innerCode)
                    freshString = True
                elif char == ']' and self.code:
                    try:
                        line, i, char = next(sIter)
                        self._raw += char
                    except StopIteration:
                        stopIter = True
                    else:
                        if char == '(':
                            self.tokens = ''
                            inBraces = True
                            self._contents.append((currentLine, currentIndex, currentString))
                            self._raw = self._raw[:-2]
                        elif char == '[':
                            self._contents.append((currentLine, currentIndex, currentString))
                            innerCode = Node(sIter, line, i, char, self.file)
                            self._raw += innerCode.raw
                            self._contents.append(innerCode)
                            self.code = False
                            stopIter = True
                        else:
                            currentString += ']' + char
                            self._contents.append((currentLine, currentIndex, currentString))
                            stopIter = True
                            self.code = False
                else:
                    currentString += char

        for val in self._contents:
            if isinstance(val, Node):
                self.contents.append(val)
            elif isinstance(val, tuple):
                self.contents.append(val[2])
            else:
                raise CodeParserException("Unxepected object: {} in _contents".format(val))

    def __add__(self, other):
        tmpSelf = copy.copy(self)
        tmpSelf._contents.append(other._contents)
        tmpSelf.contents.append(other.contents)
        #reset the memoizations
        tmpSelf._children = None
        tmpSelf._containedSections = None
        tmpSelf._tagSections = None
        tmpSelf._codes = None
        return tmpSelf

    def __iadd__(self, other):
        self._contents.append(other._contents)
        self.contents.append(other.contents)
        #reset the memoizations
        self._children = None
        self._containedSections = None
        self._tagSections = None
        self._codes = None
        return self

    @property
    def raw(self):
        #TODO Consider how to handle this
        return self._raw

    @property
    def children(self):
        if self._children is None:
            children = []
            for val in self._contents:
                if isinstance(val, tuple):
                    pass
                elif isinstance(val, Node):
                    children.append(val)
                else:
                    raise CodeParserException("Node {} contains a non-Node, non-string object: {}".format(self, val))
            self._children = children
        return self._children

    @property
    def containedSections(self):
        if self._containedSections is None:
            self._containedSections = self.codes
            for child in self.children:
                self._containedSections += child.codes
        return self._containedSections

    @property
    def tagSections(self):
        if self._tagSections is None:
            self._tagSections = self.codes
            for c in self.children:
                self._tagSections += c.tagSections
        return self._tagSections

    @property
    def codes(self):
        def readCodes(codeStr):
            codes = codeStr.split(' ')
            retCodes = []
            for code in codes:
                if len(code) > 1 and code[0] in codeSectionTypes:
                    retCodes.append((code[0], code))
            return retCodes

        if self._codes is None:
            self._codes = []
            if self.code:
                tagStrings = readCodes(self.tokens)
                for codeChar, code in tagStrings:
                    self._codes.append(codeSectionTypes[codeChar](self._contents, code, self.line, self.index, self.raw, self.file))
        return self._codes

    def __repr__(self):
        if self.code:
            s = "< Node [{}]({}) >".format(len(self._raw), self.tokens)
        else:
            s = "< Node [{}] >".format(len(self._raw))
        return s

class CodeSection(object):
    def __init__(self, contents, tag, startLine, startIndex, startRaw, filePath):
        self.contents = contents
        self.tag = tag
        self.line = startLine
        self.index = startIndex
        self.file = filePath
        self._raw = startRaw
        self._children = None

    def __repr__(self):
        s = "< CodeSection [{}]({}) >".format(len(self._raw), self.tag)
        return s

    def __str__(self):
        s = "From {}\nLine {}\tCharacter Number {}\tLength {}\n{}".format(self.file, self.line, self.index + 1, len(self), self.raw)
        return s

    def __hash__(self):
        return hash(self.raw + self.tag + str(self.index))

    def __len__(self):
        return len(self.raw)

    def __contains__(self, tag):
        for c in self.children:
            if c.tag == tag:
                return True
        return False

    def __getitem__(self, tag):
        retTags = []
        for c in self.children:
            for sec in c.codes:
                if sec.tag == tag:
                    retTags.append(sec)
        return retTags

    @property
    def raw(self):
        return self._raw

    @property
    def children(self):
        if self._children is None:
            children = []
            for val in self.contents:
                if isinstance(val, tuple):
                    pass
                elif isinstance(val, Node):
                    children.append(val)
                else:
                    raise CodeParserException("Node {} contains a non-Node, non-string object: {}".format(self, val))
            self._children = children
        return self._children

class ContextCodeSection(CodeSection):
    pass

class ContentCodeSection(CodeSection):
    pass

class MetaCodeSection(CodeSection):
    pass

codeSectionTypes = {
    contextChar : ContextCodeSection,
    contentChar : ContentCodeSection,
    metaChar : MetaCodeSection,
}

class Tag(object):
    def __init__(self, sections, tag):
        for s in sections:
            if s.tag != tag:
                raise CodeParserException("Tag objects can ony be made from CodeSections with the same tag. A tag of {} was found when {} was expected".format(s.tag, tag))
        self.sections = sections
        self._containedTags = None
        self._containedSections = None
        self._raw = None
        self.tag = tag
        self.description = None
        self.extraInfo = None
        self.unDocumented = True

    def __add__(self, other):
        if self.tag != other.tag:
            raise CodeParserException("Tags can only be added togehter if they have the same tag string, {} cannot be added to {}".format(self.tag, other.tag))
        return Tag(self.tag, self.sections + other.sections)

    def __len__(self):
        return len(self.sections)

    def __getitem__(self, tag):
        retSections = []
        for sec in self.sections:
            retSections += sec[tag]
        return retSections

    @property
    def raw(self):
        if self._raw is None:
            self._raw = []
            for sec in self.sections:
                self._raw.append(sec.raw)
        return self._raw

    @property
    def containedSections(self):
        if self._containedSections is None:
            self._containedSections = []
            for sec in self.sections:
                for seg in [node.containedSections for node in sec.children]:
                    self._containedSections += seg
        return self._containedSections

    @property
    def containedTags(self):
        if self._containedTags is None:
            self._containedTags = []
            for sec in self.containedSections:
                if sec.tag not in self._containedTags:
                    self._containedTags.append(sec.tag)
        return self._containedTags

    def __repr__(self):
        if self.unDocumented:
            s = "< {} {} [unDocumented] >".format(type(self).__qualname__, self.tag)
        elif self.description:
            s = "< {} {} [{}] >".format(type(self).__qualname__, self.tag, self.description)
        else:
            s = "< {} {} [No Description] >".format(type(self).__qualname__, self.tag)
        return s

    def __str__(self):
        s = "{}\t{}\tcount {}\t: ".format(type(self).__qualname__, self.tag, len(self))
        if self.unDocumented:
            s += "unDocumented"
        elif self.description:
            s += "{}".format(self.description)
        else:
            s += "No Description"
        return s

    def addDocs(self, dataDict):
        if 'description' in dataDict:
            self.description = dataDict.pop('description')
        if len(dataDict) > 0:
            self.extraInfo = dataDict
        self.unDocumented = False

class ContextCode(Tag):
    pass

class ContentCode(Tag):
    pass

class MetaCode(Tag):
    pass

codeTypes = {
    contextChar : ContextCode,
    contentChar : ContentCode,
    metaChar : MetaCode,
}

def makeCode(tagString, sections = None, dataDict = None):
    if sections is None:
        sections = []
    try:
        tag = codeTypes[tagString[0]](sections, tagString)
    except KeyError:
        raise KeyError("{} is not the begining of a code.".format(tagString[0]))
    if dataDict is not None:
        tag.addDocs(dataDict)
    return tag
