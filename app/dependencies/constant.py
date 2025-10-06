from enum import Enum


class Status(Enum):
        APPLICATION = 'APPLICATION'
        WAITFORPAY = 'WAITFORPAY'
        VALIDATESLIP='VALIDATESLIP'
        MERCHANT='MERCHANT'
        RETIRE='RETIRE'
        ALL='ALL'
        
ALL_STATUS=[Status.APPLICATION.name,Status.WAITFORPAY.name,Status.VALIDATESLIP.name,Status.MERCHANT.name,Status.RETIRE.name,Status.ALL.name]