from .init import startInit
from .status import startStatus
from .add import startAdd
from .table import startTable
from .sync import startSync
from .tag import startTag
from .organize import startOrganize

subCommands = {
    "init" : startInit,
    "status" : startStatus,
    "add" : startAdd,
    "table" : startTable,
    "sync" : startSync,
    "tag" : startTag,
    "organize" : startOrganize,
}
