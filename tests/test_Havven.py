import unittest
from utils.deployutils import attempt, compile_contracts, attempt_deploy, W3, mine_txs, mine_tx, \
    UNIT, MASTER, DUMMY, to_seconds, fast_forward, fresh_account, fresh_accounts, take_snapshot, restore_snapshot
from utils.testutils import assertReverts, block_time, assertClose, generate_topic_event_map, get_event_data_from_log

SOLIDITY_SOURCES = ["tests/contracts/PublicHavven.sol", "contracts/EtherNomin.sol",
                    "contracts/Court.sol"]


def deploy_public_havven():
    print("Deployment initiated.\n")

    compiled = attempt(compile_contracts, [SOLIDITY_SOURCES], "Compiling contracts... ")

    # Deploy contracts
    havven_contract, hvn_txr = attempt_deploy(compiled, 'PublicHavven',
                                              MASTER, [MASTER])
    hvn_block = W3.eth.blockNumber
    nomin_contract, nom_txr = attempt_deploy(compiled, 'EtherNomin',
                                             MASTER,
                                             [havven_contract.address, MASTER, MASTER,
                                              1000 * UNIT, MASTER])
    court_contract, court_txr = attempt_deploy(compiled, 'Court',
                                               MASTER,
                                               [havven_contract.address, nomin_contract.address,
                                                MASTER])

    # Hook up each of those contracts to each other
    txs = [havven_contract.functions.setNomin(nomin_contract.address).transact({'from': MASTER}),
           nomin_contract.functions.setCourt(court_contract.address).transact({'from': MASTER})]
    attempt(mine_txs, [txs], "Linking contracts... ")

    havven_event_dict = generate_topic_event_map(compiled['PublicHavven']['abi'])

    print("\nDeployment complete.\n")
    return havven_contract, nomin_contract, court_contract, hvn_block, havven_event_dict


def setUpModule():
    print("Testing Havven...")


def tearDownModule():
    print()


class TestHavven(unittest.TestCase):
    def setUp(self):
        self.snapshot = take_snapshot()
        time_remaining = self.targetFeePeriodDurationSeconds() + self.feePeriodStartTime() - block_time()
        fast_forward(time_remaining + 1)
        self.recomputeLastAverageBalance(MASTER)

    def tearDown(self):
        restore_snapshot(self.snapshot)

    @classmethod
    def setUpClass(cls):
        cls.assertClose = assertClose
        cls.assertReverts = assertReverts
        # to avoid overflowing in the negative direction (now - targetFeePeriodDuration * 2)
        fast_forward(weeks=102)

        cls.havven, cls.nomin, cls.court, cls.construction_block, cls.havven_event_dict = deploy_public_havven()

        # INHERITED
        # OWNED
        # owner
        cls.owner = lambda self: self.havven.functions.owner().call()
        # setOwner
        cls.setOwner = lambda self, sender, addr: mine_tx(
            self.havven.functions.setOwner(addr).transact({'from': sender}))

        # ERC20TOKEN (transfer/transferFrom are overwritten)
        # totalSupply
        cls.totalSupply = lambda self: self.havven.functions.totalSupply().call()
        cls.name = lambda self: self.havven.functions.name().call()
        cls.symbol = lambda self: self.havven.functions.symbol().call()
        cls.balanceOf = lambda self, a: self.havven.functions.balanceOf(a).call()
        cls.allowance = lambda self, owner, spender: self.havven.functions.allowance(owner, spender).call()
        cls.approve = lambda self, sender, spender, val: mine_tx(
            self.havven.functions.approve(spender, val).transact({"from": sender}))

        # HAVVEN
        # GETTERS
        cls.currentBalanceSum = lambda self, addr: self.havven.functions._currentBalanceSum(addr).call()
        cls.lastAverageBalance = lambda self, addr: self.havven.functions.lastAverageBalance(addr).call()
        cls.penultimateAverageBalance = lambda self, addr: self.havven.functions.penultimateAverageBalance(addr).call()
        cls.lastTransferTimestamp = lambda self, addr: self.havven.functions._lastTransferTimestamp(addr).call()
        cls.hasWithdrawnLastPeriodFees = lambda self, addr: self.havven.functions._hasWithdrawnLastPeriodFees(
            addr).call()
        cls.lastAverageBalanceNeedsRecomputation = lambda self, addr: self.havven.functions.lastAverageBalanceNeedsRecomputation(addr).call()

        cls.feePeriodStartTime = lambda self: self.havven.functions.feePeriodStartTime().call()
        cls.lastFeePeriodStartTime = lambda self: self.havven.functions._lastFeePeriodStartTime().call()
        cls.penultimateFeePeriodStartTime = lambda self: self.havven.functions._penultimateFeePeriodStartTime().call()
        cls.targetFeePeriodDurationSeconds = lambda self: self.havven.functions.targetFeePeriodDurationSeconds().call()
        cls.minFeePeriodDurationSeconds = lambda self: self.havven.functions._minFeePeriodDurationSeconds().call()
        cls.maxFeePeriodDurationSeconds = lambda self: self.havven.functions._maxFeePeriodDurationSeconds().call()
        cls.lastFeesCollected = lambda self: self.havven.functions.lastFeesCollected().call()

        cls.get_nomin = lambda self: self.havven.functions.nomin().call()

        #
        # SETTERS
        cls.setNomin = lambda self, sender, addr: mine_tx(
            self.havven.functions.setNomin(addr).transact({'from': sender}))
        cls.setTargetFeePeriodDuration = lambda self, sender, dur: mine_tx(
            self.havven.functions.setTargetFeePeriodDuration(dur).transact({'from': sender}))

        #
        # FUNCTIONS
        cls.endow = lambda self, sender, addr, amt: mine_tx(
            self.havven.functions.endow(addr, amt).transact({'from': sender}))
        cls.transfer = lambda self, sender, addr, amt: mine_tx(
            self.havven.functions.transfer(addr, amt).transact({'from': sender}))
        cls.transferFrom = lambda self, sender, frm, to, amt: mine_tx(
            self.havven.functions.transferFrom(frm, to, amt).transact({'from': sender}))
        cls.recomputeLastAverageBalance = lambda self, sender: mine_tx(
            self.havven.functions.recomputeLastAverageBalance().transact({'from': sender}))
        cls.rolloverFeePeriod = lambda self, sender: mine_tx(
            self.havven.functions.rolloverFeePeriod().transact({'from': sender}))

        #
        # INTERNAL
        cls.adjustFeeEntitlement = lambda self, sender, acc, p_bal: mine_tx(
            self.havven.functions._adjustFeeEntitlement(acc, p_bal).transact({'from': sender}))
        # rolloverFee (ltt->last_transfer_time)
        cls.rolloverFee = lambda self, sender, acc, ltt, p_bal: mine_tx(
            self.havven.functions._rolloverFee(acc, ltt, p_bal).transact({'from': sender}))

        # withdrawFeeEntitlement
        cls.withdrawFeeEntitlement = lambda self, sender: mine_tx(
            self.havven.functions.withdrawFeeEntitlement().transact({'from': sender}))

        #
        # MODIFIERS
        # postCheckFeePeriodRollover
        cls._checkFeePeriodRollover = lambda self, sender: mine_tx(
            self.havven.functions._checkFeePeriodRollover().transact({'from': sender}))

    def start_new_fee_period(self):
        time_remaining = self.targetFeePeriodDurationSeconds() + self.feePeriodStartTime() - block_time()
        fast_forward(time_remaining + 1)
        self._checkFeePeriodRollover(MASTER)

    ###
    # Test inherited Owned - Should be the same test_Owned.py
    ###
    def test_owner_is_master(self):
        self.assertEqual(self.owner(), MASTER)

    def test_change_owner(self):
        old_owner = self.owner()
        new_owner = DUMMY

        self.setOwner(old_owner, new_owner)
        self.assertEqual(self.owner(), new_owner)

        # reset back to old owner
        self.setOwner(new_owner, old_owner)
        self.assertEqual(self.owner(), old_owner)

    def test_change_invalid_owner(self):
        invalid_account = DUMMY
        self.assertReverts(self.setOwner, invalid_account, invalid_account)

    ###
    # Test inherited ERC20Token
    ###
    # Constuctor
    def test_ERC20Token_constructor(self):
        total_supply = 10 ** 8 * UNIT
        self.assertEqual(self.name(), "Havven")
        self.assertEqual(self.symbol(), "HAV")
        self.assertEqual(self.totalSupply(), total_supply)
        self.assertEqual(self.balanceOf(self.havven.address), total_supply)

    # Approval
    def test_approve(self):
        owner = MASTER
        spender = DUMMY
        self.approve(owner, spender, UNIT)
        self.assertEquals(self.allowance(owner, spender), UNIT)
        self.approve(owner, spender, 0)
        self.assertEquals(self.allowance(owner, spender), 0)

    #
    ##
    ###
    # Test Havven
    ###
    ###
    # Constructor
    ###
    def test_constructor(self):
        fee_period = self.targetFeePeriodDurationSeconds()
        self.assertEquals(fee_period, to_seconds(weeks=4))
        self.assertGreater(block_time(), 2 * fee_period)
        self.assertEquals(self.minFeePeriodDurationSeconds(), to_seconds(days=1))
        self.assertEquals(self.maxFeePeriodDurationSeconds(), to_seconds(weeks=26))
        self.assertEquals(self.lastFeesCollected(), 0)
        self.assertEquals(self.get_nomin(), self.nomin.address)

    ###
    # Mappings
    ###
    # currentBalanceSum
    def test_currentBalanceSum(self):
        """
        Testing the value of currentBalanceSum works as intended,
        Further testing involving this and fee collection will be done
        in scenario testing
        """
        fee_period = self.targetFeePeriodDurationSeconds()
        delay = int(fee_period / 10)
        alice = fresh_account()
        self.assertEquals(self.balanceOf(alice), 0)

        start_amt = UNIT * 50
        self.endow(MASTER, alice, start_amt)
        self.assertEquals(self.balanceOf(alice), start_amt)
        self.assertEquals(self.currentBalanceSum(alice), 0)
        start_time = block_time()
        fast_forward(delay)
        self.adjustFeeEntitlement(alice, alice, self.balanceOf(alice))
        end_time = block_time()
        balance_sum = (end_time - start_time) * start_amt
        self.assertEquals(
            self.currentBalanceSum(alice),
            balance_sum
        )
        self.transfer(alice, self.havven.address, start_amt)
        self.assertEquals(self.balanceOf(alice), 0)
        fast_forward(delay)
        self.adjustFeeEntitlement(alice, alice, self.balanceOf(alice))
        self.assertClose(
            self.currentBalanceSum(alice), balance_sum
        )

    # lastAverageBalance
    def test_lastAverageBalance(self):
        # set the block time to be at least 30seconds away from the end of the fee_period
        fee_period = self.targetFeePeriodDurationSeconds()
        time_remaining = self.targetFeePeriodDurationSeconds() + self.feePeriodStartTime() - block_time()
        if time_remaining < 30:
            fast_forward(50)
            time_remaining = self.targetFeePeriodDurationSeconds() + self.feePeriodStartTime() - block_time()

        # fast forward next block with some extra padding
        delay = time_remaining + 100
        alice = fresh_account()
        self.assertEquals(self.balanceOf(alice), 0)

        start_amt = UNIT * 50

        tx_receipt = self.endow(MASTER, alice, start_amt)
        self.assertEquals(self.balanceOf(alice), start_amt)
        self.assertEquals(self.currentBalanceSum(alice), 0)
        self.assertEquals(self.lastAverageBalance(alice), 0)
        self.assertEquals(self.lastTransferTimestamp(alice), block_time(tx_receipt['blockNumber']))
        fast_forward(delay)
        self._checkFeePeriodRollover(DUMMY)
        fast_forward(fee_period // 2)

        tx_receipt = self.adjustFeeEntitlement(alice, alice, self.balanceOf(alice))
        block_number = tx_receipt['blockNumber']

        duration_since_rollover = block_time(block_number) - self.feePeriodStartTime()
        balance_sum = duration_since_rollover * start_amt

        actual = self.currentBalanceSum(alice)
        expected = balance_sum
        self.assertClose(
            actual, expected
        )

        time_remaining = self.targetFeePeriodDurationSeconds() + self.feePeriodStartTime() - block_time()
        fast_forward(time_remaining - 5)
        self.transfer(alice, MASTER, start_amt // 2)
        time_remaining = self.targetFeePeriodDurationSeconds() + self.feePeriodStartTime() - block_time()
        fast_forward(time_remaining + 10)

        actual = self.lastAverageBalance(alice)
        expected = (start_amt * delay) // (self.feePeriodStartTime() - self.lastFeePeriodStartTime())
        self.assertClose(
            actual, expected
        )

    def test_lastAverageBalanceFullPeriod(self):
        alice = fresh_account()
        fee_period = self.targetFeePeriodDurationSeconds()

        # Alice will initially have 20 havvens
        self.endow(MASTER, alice, 20 * UNIT)
        self.assertEquals(self.balanceOf(alice), 20 * UNIT)

        # Fastforward until just before a fee period rolls over.
        time_remaining = self.targetFeePeriodDurationSeconds() + self.feePeriodStartTime() - block_time()
        fast_forward(time_remaining + 50)
        tx_receipt = self.transfer(alice, alice, 0)
        self.assertEquals(self.lastTransferTimestamp(alice), block_time(tx_receipt['blockNumber']))
        event = get_event_data_from_log(self.havven_event_dict, tx_receipt.logs[0])
        self.assertEqual(event['event'], 'FeePeriodRollover')

        # roll over the full period
        fast_forward(fee_period + 50)
        tx_receipt = self.transfer(alice, alice, 0)
        event = get_event_data_from_log(self.havven_event_dict, tx_receipt.logs[0])
        self.assertEqual(event['event'], 'FeePeriodRollover')
        self.assertEquals(self.lastTransferTimestamp(alice), block_time(tx_receipt['blockNumber']))
        self.assertEqual(self.lastAverageBalance(alice), 20 * UNIT)

        # Try a half-and-half period
        time_remaining = self.targetFeePeriodDurationSeconds() + self.feePeriodStartTime() - block_time()
        fast_forward(time_remaining + 50)
        self.transfer(alice, MASTER, 10 * UNIT)
        event = get_event_data_from_log(self.havven_event_dict, tx_receipt.logs[0])
        self.assertEqual(event['event'], 'FeePeriodRollover')
        fast_forward(fee_period // 2)
        tx_receipt = self.transfer(alice, MASTER, 10 * UNIT)
        fast_forward(fee_period // 2 + 10)
        self.recomputeLastAverageBalance(alice)
        self.assertClose(self.lastAverageBalance(alice), 5 * UNIT)

    def test_arithmeticSeriesBalance(self):
        alice = fresh_account()
        fee_period = self.targetFeePeriodDurationSeconds()
        n = 50

        self.endow(MASTER, alice, n * UNIT)
        time_remaining = self.targetFeePeriodDurationSeconds() + self.feePeriodStartTime() - block_time()
        fast_forward(time_remaining + 5)

        for _ in range(n):
            self.transfer(alice, MASTER, UNIT)
            fast_forward(fee_period // n)

        self.recomputeLastAverageBalance(alice)
        self.assertClose(self.lastAverageBalance(alice), n*(n-1) * UNIT // (2*n))

    def test_averageBalanceSum(self):
        alice, bob, carol = fresh_accounts(3)
        fee_period = self.targetFeePeriodDurationSeconds()

        self.endow(MASTER, alice, UNIT)

        self.start_new_fee_period()

        self.transfer(alice, bob, UNIT // 4)
        self.transfer(alice, carol, UNIT // 4)
        fast_forward(fee_period // 10)
        self.transfer(bob, carol, UNIT // 4)
        fast_forward(fee_period // 10)
        self.transfer(carol, bob, UNIT // 2)
        fast_forward(fee_period // 10)
        self.transfer(bob, alice, UNIT // 4)
        fast_forward(2 * fee_period // 10)
        self.transfer(alice, bob, UNIT // 3)
        self.transfer(alice, carol, UNIT // 3)
        fast_forward(3 * fee_period // 10)
        self.transfer(carol, bob, UNIT // 3)
        fast_forward(3 * fee_period // 10)

        self.recomputeLastAverageBalance(alice)
        self.recomputeLastAverageBalance(bob)
        self.recomputeLastAverageBalance(carol)

        total_average = self.lastAverageBalance(alice) + \
                        self.lastAverageBalance(bob) + \
                        self.lastAverageBalance(carol)

        self.assertClose(UNIT, total_average)

    # penultimateAverageBalance
    def test_penultimateAverageBalance(self):
        # start a new fee period
        alice = fresh_account()
        fee_period = self.targetFeePeriodDurationSeconds()
        fast_forward(fee_period * 2)
        self._checkFeePeriodRollover(DUMMY)

        # skip to halfway through it
        delay = fee_period // 2
        fast_forward(delay)

        self.assertEquals(self.balanceOf(alice), 0)

        start_amt = UNIT * 50

        self.endow(MASTER, alice, start_amt)
        inital_transfer_time = self.lastTransferTimestamp(alice)
        self.assertEquals(self.balanceOf(alice), start_amt)
        self.assertEquals(self.currentBalanceSum(alice), 0)
        self.assertEquals(self.lastAverageBalance(alice), 0)

        # rollover two fee periods without alice doing anything
        fast_forward(fee_period * 2)
        self._checkFeePeriodRollover(DUMMY)

        fast_forward(fee_period * 2)
        self._checkFeePeriodRollover(DUMMY)

        # adjust alice's fee entitlement
        self.adjustFeeEntitlement(alice, alice, self.balanceOf(alice))

        # expected currentBalance sum is balance*(time since start of period)
        actual = self.currentBalanceSum(alice)
        expected = (block_time() - self.feePeriodStartTime()) * start_amt
        self.assertClose(
            actual, expected
        )

        last_period_delay = (self.feePeriodStartTime() - self.lastFeePeriodStartTime())

        actual = self.lastAverageBalance(alice)
        expected = (start_amt * last_period_delay) // last_period_delay
        self.assertClose(
            actual, expected,
            msg='last:'
        )

        delay_from_transfer = self.lastFeePeriodStartTime() - inital_transfer_time
        penultimate_period_duration = self.lastFeePeriodStartTime() - self.penultimateFeePeriodStartTime()

        actual = self.penultimateAverageBalance(alice)
        expected = (start_amt * delay_from_transfer) // penultimate_period_duration
        self.assertClose(
            actual, expected,
            msg='penultimate:'
        )

    # lastTransferTimestamp - tested above
    # hasWithdrawnLastPeriodFees - tested in test_FeeCollection.py
    # lastFeesCollected - tested in test_FeeCollection.py

    ###
    # Contract variables
    ###
    # feePeriodStartTime - tested above
    # targetFeePeriodDurationSeconds - tested above
    # minFeePeriodDurationSeconds - constant, checked in constructor test

    ###
    # Functions
    ###

    # setNomin
    def test_SetNomin(self):
        alice = fresh_account()
        self.setNomin(MASTER, alice)
        self.assertEqual(self.get_nomin(), alice)

    def test_invalidSetNomin(self):
        alice = fresh_account()
        self.assertReverts(self.setNomin, alice, alice)

    # setTargetFeePeriod
    def test_setTargetFeePeriod(self):
        self.setTargetFeePeriodDuration(MASTER, to_seconds(weeks=10))
        self.assertEqual(
            self.targetFeePeriodDurationSeconds(),
            to_seconds(weeks=10)
        )

    def test_setTargetFeePeriod_max(self):
        sixmonths = 26 * 7 * 24 * 60 * 60
        self.assertReverts(self.setTargetFeePeriodDuration, MASTER, 2**256 - 1)
        self.assertReverts(self.setTargetFeePeriodDuration, MASTER, sixmonths + 1)
        self.setTargetFeePeriodDuration(MASTER, sixmonths)
        self.assertEqual(
            self.targetFeePeriodDurationSeconds(),
            sixmonths
        )

    def test_setTargetFeePeriod_minimal(self):
        self.setTargetFeePeriodDuration(MASTER, self.minFeePeriodDurationSeconds())
        self.assertEqual(
            self.targetFeePeriodDurationSeconds(),
            self.minFeePeriodDurationSeconds()
        )

    def test_setTargetFeePeriod_invalid_below_min(self):
        self.assertReverts(self.setTargetFeePeriodDuration, MASTER, self.minFeePeriodDurationSeconds() - 1)

    def test_setTargetFeePeriod_invalid_0(self):
        self.assertReverts(self.setTargetFeePeriodDuration, MASTER, self.minFeePeriodDurationSeconds() - 1)

    # endow
    def test_endow_valid(self):
        amount = 50 * UNIT
        havven_balance = self.balanceOf(self.havven.address)
        alice = fresh_account()
        self.assertEquals(self.balanceOf(alice), 0)
        self.endow(MASTER, alice, amount)
        self.assertEquals(self.balanceOf(alice), amount)
        self.assertEquals(havven_balance - self.balanceOf(self.havven.address), amount)

    def test_endow_0(self):
        amount = 0
        havven_balance = self.balanceOf(self.havven.address)
        alice = fresh_account()
        self.assertEquals(self.balanceOf(alice), 0)
        self.endow(MASTER, alice, amount)
        self.assertEquals(self.balanceOf(alice), amount)
        self.assertEquals(havven_balance - self.balanceOf(self.havven.address), amount)

    def test_endow_supply(self):
        amount = self.totalSupply()
        havven_balance = self.balanceOf(self.havven.address)
        alice = fresh_account()
        self.assertEquals(self.balanceOf(alice), 0)
        self.endow(MASTER, alice, amount)
        self.assertEquals(self.balanceOf(alice), amount)
        self.assertEquals(havven_balance - self.balanceOf(self.havven.address), amount)

    def test_endow_more_than_supply(self):
        amount = self.totalSupply() * 2
        alice = fresh_account()
        self.assertReverts(self.endow, MASTER, alice, amount)
        self.assertEquals(self.balanceOf(alice), 0)

    def test_endow_invalid_sender(self):
        amount = 50 * UNIT
        alice = fresh_account()
        self.assertReverts(self.endow, alice, alice, amount)
        self.assertEquals(self.balanceOf(alice), 0)

    def test_endow_contract_sender(self):
        amount = 50 * UNIT
        alice = fresh_account()
        self.assertReverts(self.endow, self.havven.address, alice, amount)
        self.assertEquals(self.balanceOf(alice), 0)

    def test_endow_to_contract(self):
        amount = 50 * UNIT
        self.assertEqual(self.balanceOf(self.havven.address), self.totalSupply())
        self.endow(MASTER, self.havven.address, amount)
        self.assertEqual(self.balanceOf(self.havven.address), self.totalSupply())
        # Balance is not lost (still distributable) if sent to the contract.
        self.endow(MASTER, self.havven.address, amount)

    def test_endow_currentBalanceSum(self):
        amount = 50 * UNIT
        # Force updates.
        self.endow(MASTER, self.havven.address, 0)
        havven_balanceSum = self.currentBalanceSum(self.havven.address)
        alice = fresh_account()
        fast_forward(seconds=60)
        self.endow(MASTER, alice, amount)
        self.assertGreater(self.currentBalanceSum(self.havven.address), havven_balanceSum)

    def test_endow_transfers(self):
        alice = fresh_account()
        self.recomputeLastAverageBalance(MASTER)
        tx_receipt = self.endow(MASTER, alice, 50 * UNIT)
        event = get_event_data_from_log(self.havven_event_dict, tx_receipt.logs[0])
        self.assertEqual(event['event'], 'Transfer')

    # transfer
    def test_transferRollsOver(self):
        alice = fresh_account()
        self.endow(MASTER, alice, 50 * UNIT)
        fast_forward(seconds=self.targetFeePeriodDurationSeconds() + 100)
        tx_receipt = self.transfer(alice, MASTER, 25 * UNIT)
        event = get_event_data_from_log(self.havven_event_dict, tx_receipt.logs[0])
        self.assertEqual(event['event'], 'FeePeriodRollover')

    # same as test_ERC20
    def test_transfer(self):
        sender, receiver, no_tokens = fresh_accounts(3)
        self.endow(MASTER, sender, 50 * UNIT)
        sender_balance = self.balanceOf(sender)

        receiver_balance = self.balanceOf(receiver)
        self.assertEqual(receiver_balance, 0)

        value = 10 * UNIT
        total_supply = self.totalSupply()

        # This should fail because receiver has no tokens
        self.assertReverts(self.transfer, receiver, sender, value)

        self.transfer(sender, receiver, value)
        self.assertEqual(self.balanceOf(receiver), receiver_balance + value)
        self.assertEqual(self.balanceOf(sender), sender_balance - value)

        # transfers should leave the supply unchanged
        self.assertEqual(self.totalSupply(), total_supply)

        value = 1001 * UNIT
        # This should fail because balance < value and balance > totalSupply
        self.assertReverts(self.transfer, sender, receiver, value)

        # 0 value transfers are allowed.
        value = 0
        pre_sender_balance = self.balanceOf(sender)
        pre_receiver_balance = self.balanceOf(receiver)
        self.transfer(sender, receiver, value)
        self.assertEqual(self.balanceOf(receiver), pre_receiver_balance)
        self.assertEqual(self.balanceOf(sender), pre_sender_balance)

        # It is also possible to send 0 value transfer from an account with 0 balance.
        self.assertEqual(self.balanceOf(no_tokens), 0)
        self.transfer(no_tokens, receiver, value)
        self.assertEqual(self.balanceOf(no_tokens), 0)

    # transferFrom
    def test_transferFromRollsOver(self):
        alice = fresh_account()
        self.endow(MASTER, alice, 50 * UNIT)
        self.approve(alice, MASTER, 25 * UNIT)
        fast_forward(seconds=self.targetFeePeriodDurationSeconds() + 100)
        tx_receipt = self.transferFrom(MASTER, alice, MASTER, 25 * UNIT)
        event = get_event_data_from_log(self.havven_event_dict, tx_receipt.logs[0])
        self.assertEqual(event['event'], 'FeePeriodRollover')

    def test_transferFrom(self):
        approver, spender, receiver, no_tokens = fresh_accounts(4)

        self.endow(MASTER, approver, 50 * UNIT)

        approver_balance = self.balanceOf(approver)
        spender_balance = self.balanceOf(spender)
        receiver_balance = self.balanceOf(receiver)

        value = 10 * UNIT
        total_supply = self.totalSupply()

        # This fails because there has been no approval yet
        self.assertReverts(self.transferFrom, spender, approver, receiver, value)

        self.approve(approver, spender, 2 * value)
        self.assertEqual(self.allowance(approver, spender), 2 * value)

        self.assertReverts(self.transferFrom, spender, approver, receiver, 2 * value + 1)
        self.transferFrom(spender, approver, receiver, value)

        self.assertEqual(self.balanceOf(approver), approver_balance - value)
        self.assertEqual(self.balanceOf(spender), spender_balance)
        self.assertEqual(self.balanceOf(receiver), receiver_balance + value)
        self.assertEqual(self.allowance(approver, spender), value)
        self.assertEqual(self.totalSupply(), total_supply)

        # Empty the account
        self.transferFrom(spender, approver, receiver, value)

        # This account has no tokens
        approver_balance = self.balanceOf(no_tokens)
        self.assertEqual(approver_balance, 0)
        self.assertEqual(self.allowance(no_tokens, spender), 0)

        self.approve(no_tokens, spender, value)
        self.assertEqual(self.allowance(no_tokens, spender), value)

        # This should fail because the approver has no tokens.
        self.assertReverts(self.transferFrom, spender, no_tokens, receiver, value)

    def test_double_withdraw_fee(self):
        alice = fresh_account()
        self.withdrawFeeEntitlement(alice)
        self.assertReverts(self.withdrawFeeEntitlement, alice)

    def test_withdraw_multiple_periods(self):
        alice = fresh_account()
        self.withdrawFeeEntitlement(alice)
        fast_forward(self.targetFeePeriodDurationSeconds()*2)
        self.rolloverFeePeriod(DUMMY)
        self.withdrawFeeEntitlement(alice)
        fast_forward(self.targetFeePeriodDurationSeconds()*2)
        self.rolloverFeePeriod(DUMMY)

    # adjustFeeEntitlement - tested above
    # rolloverFee - tested above, indirectly

    # withdrawFeeEntitlement - tested in test_FeeCollection.py

    ###
    # Modifiers
    ###
    # postCheckFeePeriodRollover - tested above

    def test_abuse_havven_balance(self):
        """Test whether repeatedly moving havvens between two parties will shift averages upwards"""
        alice, bob = fresh_accounts(2)
        amount = UNIT * 100000
        a_sum = 0
        b_sum = 0
        self.endow(MASTER, alice, amount)
        time = block_time()
        self.assertEquals(self.balanceOf(alice), amount)
        self.assertEquals(self.currentBalanceSum(alice), 0)
        for i in range(20):
            self.transfer(alice, bob, amount)
            a_sum += (block_time() - time) * amount
            time = block_time()
            self.assertEquals(self.balanceOf(bob), amount)
            self.assertEquals(self.currentBalanceSum(alice), a_sum)
            self.transfer(bob, alice, amount)
            b_sum += (block_time() - time) * amount
            time = block_time()
            self.assertEquals(self.balanceOf(alice), amount)
            self.assertEquals(self.currentBalanceSum(bob), b_sum)


if __name__ == '__main__':
    unittest.main()
