from __future__ import print_function
from solc import *
from solc.exceptions import SolcError
from testrpc.client import EthTesterClient
from testrpc.client.utils import encode_data
from testrpc.client.utils import decode_hex
from ethereum.utils import sha3
from ethereum.tester import TransactionFailed
from rlp.utils import big_endian_to_int
import os

def fid(functionDef):
    end = functionDef.find("(")
    return functionDef[:end]

def runTest(contract, optimize, verbose=False):
    client = EthTesterClient()
    client.reset_evm()
    a0 = sorted(client.get_accounts())[0]
    try:
        bin = compile_source(contract,optimize=optimize).values()[0]['bin']
    except SolcError as e:
        if "Compiler error: Stack too deep" in str(e):
            return ("STACK TOO DEEP", None, None)
        if "Internal compiler error during compilation" in str(e):
            print (contract)
            print ("INTERNAL COMPILER ERROR WITH optimize =",optimize)
            print (e)
            assert False
        if verbose:
            print (e)
        return ("COMPILATION FAILED", None, None)
    try:
        txnHash = client.send_transaction(_from = a0, data = bytes(bin), value = 0)
    except TransactionFailed as e:
        if verbose:
            print (e)
        return ("SEND CONTRACT TRANSACTION FAILED", bytes(bin), None)
    txnReceipt = client.get_transaction_receipt(txnHash)
    contractAddress = txnReceipt['contractAddress']

    origBalances = {}
    
    for a in client.get_accounts():
        origBalances[a] = client.get_balance(a)        
    
    sendVal = 9999999
    
    fsig = encode_data(sha3("f()")[:4])
    try:
        val = client.call(_from = a0, to = contractAddress, data = fsig, value = sendVal)
    except TransactionFailed as e:
        balances = {}
        for a in client.get_accounts():
            balances[a] = client.get_balance(a)-origBalances[a]
        if verbose:
            print ("CALL FAILURE:")
            print (e)
        return ("CALL FAILED", bytes(bin), balances)
    balances = {}
    for a in client.get_accounts():
        balances[a] = client.get_balance(a)-origBalances[a]
    if verbose:
        print (balances)
    return (big_endian_to_int(decode_hex(val)), bytes(bin), balances)

def test(functions, verbose=False, verboseNoOpt=False, saveContract=True):
    gcontract = None
    pid = str(os.getpid())
    if verbose:
        print ("="*50)
    # Expects to receive a set of function definitions with a top-level, no-parameter, function called f()
    contract = "contract c {\n" + functions + "\n}"
    if saveContract:
        i = 0
        while (os.path.exists("contract." + pid + "." + str(i) + ".sol")):
            i += 1
        with open("contract." + pid + "." + str(i) + ".sol",'w') as f:
            f.write(contract)
    (resultNoOpt,binNoOpt,balancesNoOpt) = runTest(contract, False, verbose=verboseNoOpt)
    if (binNoOpt != None) and (len(binNoOpt) > (24 * 1024)):
        print ("NON-OPTIMIZED CONTRACT TOO LARGE")
        return None
    if resultNoOpt == "STACK TOO DEEP":
        print ("STACK TOO DEEP FOR NON-OPTIMIZING COMPILE")
        return None
    (resultOpt,binOpt,balancesOpt) = runTest(contract, True, verbose=verbose)
    if (binOpt != binNoOpt) and (binOpt != None) and (binNoOpt != None):
        print ("BINARIES DIFFER",len(binOpt),"BYTES VS.",len(binNoOpt),"BYTES NON-OPTIMIZED")
    if resultOpt != resultNoOpt:
        print ("*"*80)
        print ("MISMATCH:")
        print ("CONTRACT:")
        print (contract)
        print ("="*50)
        print ("OPTIMIZED VALUE:", resultOpt)
        print ("="*50)        
        print ("NON-OPTIMIZED VALUE:",resultNoOpt)
        print ("*"*80)        
        assert False
    if balancesOpt != balancesNoOpt:
        print ("*"*80)
        print ("MISMATCH IN BALANCES:")
        print ("CONTRACT:")
        print (contract)
        print ("="*50)
        print ("OPTIMIZED BALANCES:")
        for a in sorted(balancesOpt.keys()):
            print ("  ",a, balancesOpt[a])
        print ("="*50)        
        print ("NON-OPTIMIZED BALANCES (DIFFERING):")
        for a in sorted(balancesNoOpt.keys()):
            if balancesNoOpt[a] != balancesOpt[a]:
                print ("  ",a, balancesNoOpt[a])
        print ("*"*80)        
        assert False        
    if saveContract and resultOpt not in ["COMPILATION FAILED"]:
        i = 0
        while (os.path.exists("goodcontract." + pid + "." + str(i) + ".sol")):
            i += 1
        with open("goodcontract." + pid + "." + str(i) + ".sol",'w') as f:
            f.write(contract)
        gcontract = "goodcontract." + pid + "." + str(i) + ".sol"
    if resultOpt not in ["COMPILATION FAILED", "SEND CONTRACT TRANSACTION FAILED", "CALL FAILED"]:
        print ("SUCCESSFULLY TESTED:")
        print (contract)
        print ("RETURNED:",resultOpt)
    else:
        print (resultOpt,"FOR FUNCTIONS OF LENGTH",len(functions))
        if verbose:
            print ("*"*40)
            print ("CONTRACT:")
            print (contract)
            print ("*"*40)
    if (resultOpt == "INTERNAL COMPILER ERROR") or (resultNoOpt == "INTERNAL COMPILER ERROR"):
        print ("*"*40)        
        print (contract)
        print ("*"*40)        
        assert False
    return gcontract
    
