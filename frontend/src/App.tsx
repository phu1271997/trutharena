import React, { useState, useEffect } from 'react';
import { getGenLayerClient } from './lib/client';
import { connectWallet } from './lib/wallet';
import { ARENA_CONTRACT, REPUTATION_CONTRACT } from './lib/addresses';
import {
  Gavel,
  Swords,
  Trophy,
  ExternalLink,
  PlusCircle,
  CheckCircle2,
  AlertTriangle,
  RefreshCw
} from 'lucide-react';

interface ArenaItem {
  arena_id: string;
  creator: string;
  claim: string;
  pro_wallet: string;
  con_wallet: string;
  stake_per_side: string;
  state: string;
  current_round: number;
  verdict: string;
  confidence: number;
}

interface ArgumentItem {
  submitter: string;
  text: string;
  evidence_urls: string[];
  round_number: number;
  submitted_at_epoch: number;
}

interface ArenaDetail extends ArenaItem {
  context_urls: string[];
  reason: string;
  arguments: ArgumentItem[];
}

interface ReputationData {
  wallet: string;
  wins: number;
  losses: number;
  draws: number;
  total_matches: number;
  win_rate: number;
  tier: string;
}

export default function App() {
  const [account, setAccount] = useState<string | null>(null);
  const [balance, setBalance] = useState<string>('0');
  const [activeTab, setActiveTab] = useState<'arenas' | 'detail' | 'reputation' | 'about'>('arenas');
  const [arenas, setArenas] = useState<ArenaItem[]>([]);
  const [selectedArenaId, setSelectedArenaId] = useState<string>('1');
  const [selectedArena, setSelectedArena] = useState<ArenaDetail | null>(null);
  const [repAddress, setRepAddress] = useState<string>('');
  const [reputation, setReputation] = useState<ReputationData | null>(null);
  const [loading, setLoading] = useState<boolean>(false);
  const [consensusWaiting, setConsensusWaiting] = useState<boolean>(false);
  const [lastTxHash, setLastTxHash] = useState<string | null>(null);

  // Form states
  const [createClaim, setCreateClaim] = useState('');
  const [createContextUrl, setCreateContextUrl] = useState('');
  const [createStake, setCreateStake] = useState('0.1');
  const [createSide, setCreateSide] = useState<'PRO' | 'CON'>('PRO');
  const [showCreateModal, setShowCreateModal] = useState(false);

  const [argText, setArgText] = useState('');
  const [argUrl, setArgUrl] = useState('');
  const [stateFilter, setStateFilter] = useState('ALL');

  // Connect wallet
  const handleConnect = async () => {
    try {
      setLoading(true);
      const addr = await connectWallet();
      setAccount(addr);
      fetchBalance(addr);
    } catch (e: any) {
      alert(e.message || 'Connection failed');
    } finally {
      setLoading(false);
    }
  };

  const fetchBalance = async (addr: string) => {
    try {
      if (typeof window !== 'undefined' && window.ethereum) {
        const res: any = await window.ethereum.request({
          method: 'eth_getBalance',
          params: [addr, 'latest'],
        });
        if (res) {
          const balWei = BigInt(res);
          const balGen = Number(balWei) / 1e18;
          setBalance(balGen.toFixed(3));
        }
      }
    } catch (e) {
      console.error(e);
    }
  };

  // Fetch list of arenas
  const fetchArenas = async () => {
    try {
      const client = getGenLayerClient();
      const raw: any = await client.readContract({
        address: ARENA_CONTRACT,
        functionName: 'list_arenas',
        args: [stateFilter, 0, 50],
      });
      if (raw) {
        const list = typeof raw === 'string' ? JSON.parse(raw) : raw;
        setArenas(list);
      }
    } catch (e) {
      console.error('Fetch arenas error:', e);
    }
  };

  // Fetch single arena detail
  const fetchArenaDetail = async (id: string) => {
    try {
      setLoading(true);
      const client = getGenLayerClient();
      const raw: any = await client.readContract({
        address: ARENA_CONTRACT,
        functionName: 'get_arena',
        args: [id],
      });
      if (raw) {
        const d = typeof raw === 'string' ? JSON.parse(raw) : raw;
        setSelectedArena(d);
      }
    } catch (e) {
      console.error('Fetch detail error:', e);
    } finally {
      setLoading(false);
    }
  };

  // Fetch user reputation
  const fetchReputation = async (targetWallet: string) => {
    try {
      setLoading(true);
      const client = getGenLayerClient();
      const raw: any = await client.readContract({
        address: REPUTATION_CONTRACT,
        functionName: 'get_reputation',
        args: [targetWallet],
      });
      if (raw) {
        const data = typeof raw === 'string' ? JSON.parse(raw) : raw;
        setReputation(data);
      }
    } catch (e) {
      console.error('Fetch reputation error:', e);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchArenas();
  }, [stateFilter]);

  useEffect(() => {
    if (activeTab === 'detail' && selectedArenaId) {
      fetchArenaDetail(selectedArenaId);
    }
  }, [activeTab, selectedArenaId]);

  // Actions
  const handleCreateArena = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!account) return alert('Please connect your MetaMask wallet');
    try {
      setConsensusWaiting(true);
      const client = getGenLayerClient(account as `0x${string}`);
      const stakeWei = BigInt(Math.floor(Number(createStake) * 1e18));
      const urls = createContextUrl ? [createContextUrl] : [];

      const tx = await client.writeContract({
        address: ARENA_CONTRACT,
        functionName: 'create_arena',
        args: [createClaim, urls, Number(stakeWei), createSide],
        value: stakeWei,
      });

      setLastTxHash(tx as string);
      await (client as any).waitForTransactionReceipt({ hash: tx as any });
      alert('Arena created successfully on studionet!');
      setShowCreateModal(false);
      setCreateClaim('');
      setCreateContextUrl('');
      fetchArenas();
    } catch (e: any) {
      alert('Transaction error: ' + (e.message || String(e)));
    } finally {
      setConsensusWaiting(false);
    }
  };

  const handleJoinSide = async (arenaId: string, side: 'PRO' | 'CON', stakePerSide: string) => {
    if (!account) return alert('Please connect wallet');
    try {
      setConsensusWaiting(true);
      const client = getGenLayerClient(account as `0x${string}`);
      const stakeWei = BigInt(stakePerSide);

      const tx = await client.writeContract({
        address: ARENA_CONTRACT,
        functionName: 'join_side',
        args: [arenaId, side],
        value: stakeWei,
      });
      setLastTxHash(tx as string);
      await (client as any).waitForTransactionReceipt({ hash: tx as any });
      alert(`Successfully joined ${side} side!`);
      fetchArenaDetail(arenaId);
      fetchArenas();
    } catch (e: any) {
      alert('Join error: ' + (e.message || String(e)));
    } finally {
      setConsensusWaiting(false);
    }
  };

  const handleSubmitArgument = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!account || !selectedArena) return;
    try {
      setConsensusWaiting(true);
      const client = getGenLayerClient(account as `0x${string}`);
      const urls = argUrl ? [argUrl] : [];

      const tx = await client.writeContract({
        address: ARENA_CONTRACT,
        functionName: 'submit_argument',
        args: [selectedArena.arena_id, argText, urls], value: BigInt(0),
      });
      setLastTxHash(tx as string);
      await (client as any).waitForTransactionReceipt({ hash: tx as any });
      alert('Argument recorded on-chain!');
      setArgText('');
      setArgUrl('');
      fetchArenaDetail(selectedArena.arena_id);
    } catch (e: any) {
      alert('Submission error: ' + (e.message || String(e)));
    } finally {
      setConsensusWaiting(false);
    }
  };

  return (
    <div className="min-h-screen flex flex-col bg-[#070B14] text-gray-100">
      {/* Header */}
      <header className="border-b border-gray-800 bg-[#0B0F19]/80 backdrop-blur sticky top-0 z-40">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 h-16 flex items-center justify-between">
          <div className="flex items-center space-x-3 cursor-pointer" onClick={() => setActiveTab('arenas')}>
            <div className="w-10 h-10 rounded-xl bg-gradient-to-tr from-emerald-500 to-indigo-600 flex items-center justify-center text-xl shadow-lg shadow-emerald-500/20">
              ⚖️
            </div>
            <div>
              <div className="font-bold text-lg tracking-tight bg-gradient-to-r from-white to-gray-400 bg-clip-text text-transparent">
                TruthArena
              </div>
              <div className="text-[10px] text-emerald-400 font-medium tracking-wide">
                GENLAYER STUDIONET
              </div>
            </div>
          </div>

          <nav className="flex items-center space-x-1 sm:space-x-4 text-sm font-medium">
            <button
              onClick={() => setActiveTab('arenas')}
              className={`px-3 py-1.5 rounded-lg transition ${
                activeTab === 'arenas' ? 'bg-gray-800 text-white' : 'text-gray-400 hover:text-white'
              }`}
            >
              Debate Arenas
            </button>
            <button
              onClick={() => {
                setActiveTab('reputation');
                if (account) {
                  setRepAddress(account);
                  fetchReputation(account);
                }
              }}
              className={`px-3 py-1.5 rounded-lg transition ${
                activeTab === 'reputation' ? 'bg-gray-800 text-white' : 'text-gray-400 hover:text-white'
              }`}
            >
              Leaderboard
            </button>
            <button
              onClick={() => setActiveTab('about')}
              className={`px-3 py-1.5 rounded-lg transition ${
                activeTab === 'about' ? 'bg-gray-800 text-white' : 'text-gray-400 hover:text-white'
              }`}
            >
              How It Works
            </button>
          </nav>

          <div className="flex items-center space-x-3">
            {account ? (
              <div className="flex items-center space-x-2 bg-gray-900 border border-gray-800 px-3 py-1.5 rounded-xl text-xs">
                <span className="w-2 h-2 rounded-full bg-emerald-400 animate-pulse"></span>
                <span className="font-mono text-gray-300">
                  {account.slice(0, 6)}...{account.slice(-4)}
                </span>
                <span className="text-emerald-400 font-semibold pl-1 border-l border-gray-700">
                  {balance} GEN
                </span>
              </div>
            ) : (
              <button
                onClick={handleConnect}
                disabled={loading}
                className="bg-emerald-600 hover:bg-emerald-500 text-white text-xs font-semibold px-4 py-2 rounded-xl transition shadow-lg shadow-emerald-600/20 flex items-center space-x-1.5"
              >
                <span>Connect Wallet</span>
              </button>
            )}
          </div>
        </div>
      </header>

      {/* Low balance warning banner */}
      {account && Number(balance) === 0 && (
        <div className="bg-amber-950/40 border-b border-amber-800/60 px-4 py-2 text-xs text-amber-200 flex items-center justify-center space-x-2">
          <AlertTriangle className="w-4 h-4 text-amber-400" />
          <span>
            Connected wallet has 0 GEN on studionet. Open{' '}
            <a
              href="https://studio.genlayer.com"
              target="_blank"
              rel="noreferrer"
              className="underline font-bold text-amber-300 hover:text-white"
            >
              GenLayer Studio &rarr; Accounts panel
            </a>{' '}
            to transfer test GEN. Do NOT use the testnet faucet.
          </span>
        </div>
      )}

      {/* Consensus waiting overlay */}
      {consensusWaiting && (
        <div className="bg-indigo-950/70 border-b border-indigo-700/60 px-4 py-3 text-xs text-indigo-100 flex items-center justify-center space-x-3 animate-pulse">
          <RefreshCw className="w-4 h-4 text-indigo-400 animate-spin" />
          <div className="text-center">
            <span className="font-bold text-indigo-300">
              Waiting for AI Jury Consensus on GenLayer Studionet...
            </span>{' '}
            <span>Validators are fetching web evidence and validating semantic verdict (typically 15-30s).</span>
            {lastTxHash && (
              <a
                href={`https://genlayer-explorer.vercel.app/tx/${lastTxHash}`}
                target="_blank"
                rel="noreferrer"
                className="ml-2 underline text-indigo-300 hover:text-white inline-flex items-center"
              >
                View on Explorer <ExternalLink className="w-3 h-3 ml-1" />
              </a>
            )}
          </div>
        </div>
      )}

      {/* Main Content */}
      <main className="flex-1 max-w-7xl w-full mx-auto px-4 sm:px-6 lg:px-8 py-8">
        {/* ARENAS LIST TAB */}
        {activeTab === 'arenas' && (
          <div>
            <div className="flex flex-col md:flex-row md:items-center justify-between gap-4 mb-8">
              <div>
                <h1 className="text-2xl font-extrabold text-white tracking-tight">
                  Decentralized 1v1 Debates
                </h1>
                <p className="text-sm text-gray-400 mt-1">
                  Stake GEN on controversial claims. Provide URL evidence. AI validators read the web directly on-chain to adjudicate who won.
                </p>
              </div>

              <div className="flex items-center space-x-3">
                <div className="flex items-center bg-gray-900 border border-gray-800 rounded-xl p-1 text-xs">
                  {['ALL', 'OPEN', 'LOCKED', 'SETTLED'].map((filter) => (
                    <button
                      key={filter}
                      onClick={() => setStateFilter(filter)}
                      className={`px-3 py-1.5 rounded-lg font-medium transition ${
                        stateFilter === filter ? 'bg-emerald-600 text-white' : 'text-gray-400 hover:text-white'
                      }`}
                    >
                      {filter}
                    </button>
                  ))}
                </div>

                <button
                  onClick={() => setShowCreateModal(true)}
                  className="bg-gradient-to-r from-emerald-600 to-teal-600 hover:from-emerald-500 hover:to-teal-500 text-white text-xs font-semibold px-4 py-2.5 rounded-xl transition flex items-center space-x-2 shadow-lg shadow-emerald-600/20"
                >
                  <PlusCircle className="w-4 h-4" />
                  <span>Create Arena</span>
                </button>
              </div>
            </div>

            {/* Grid */}
            <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
              {arenas.map((a) => {
                const stakeGen = (Number(a.stake_per_side) / 1e18).toFixed(2);
                return (
                  <div
                    key={a.arena_id}
                    onClick={() => {
                      setSelectedArenaId(a.arena_id);
                      setActiveTab('detail');
                    }}
                    className="bg-gray-900/60 border border-gray-800 hover:border-emerald-500/50 rounded-2xl p-5 transition cursor-pointer flex flex-col justify-between group hover:shadow-xl hover:shadow-emerald-500/5"
                  >
                    <div>
                      <div className="flex items-center justify-between mb-3 text-xs">
                        <span className="font-mono text-gray-400">Match #{a.arena_id}</span>
                        <span
                          className={`px-2.5 py-0.5 rounded-full font-semibold text-[10px] ${
                            a.state === 'OPEN'
                              ? 'bg-amber-500/10 text-amber-400 border border-amber-500/20'
                              : a.state === 'LOCKED'
                              ? 'bg-blue-500/10 text-blue-400 border border-blue-500/20'
                              : 'bg-emerald-500/10 text-emerald-400 border border-emerald-500/20'
                          }`}
                        >
                          {a.state}
                        </span>
                      </div>

                      <h3 className="text-base font-bold text-gray-100 group-hover:text-emerald-400 transition leading-snug line-clamp-3 mb-4">
                        "{a.claim}"
                      </h3>
                    </div>

                    <div className="border-t border-gray-800/80 pt-4 mt-2">
                      <div className="flex items-center justify-between text-xs text-gray-400 mb-2">
                        <span>Stake per side:</span>
                        <span className="font-semibold text-emerald-400">{stakeGen} GEN</span>
                      </div>
                      <div className="flex items-center justify-between text-xs text-gray-400">
                        <span>Round:</span>
                        <span className="font-medium text-gray-300">
                          {a.state === 'SETTLED' ? 'Completed (3/3)' : `Round ${a.current_round} of 3`}
                        </span>
                      </div>

                      {a.verdict && (
                        <div className="mt-3 pt-3 border-t border-gray-800/60 flex items-center justify-between text-xs">
                          <span className="text-gray-400">Verdict:</span>
                          <span className="font-bold text-emerald-400 flex items-center space-x-1">
                            <CheckCircle2 className="w-3.5 h-3.5 mr-1" /> {a.verdict} ({a.confidence}%)
                          </span>
                        </div>
                      )}
                    </div>
                  </div>
                );
              })}
            </div>

            {arenas.length === 0 && (
              <div className="text-center py-16 bg-gray-900/30 rounded-2xl border border-gray-800/60">
                <Gavel className="w-12 h-12 mx-auto text-gray-600 mb-3" />
                <h3 className="text-base font-semibold text-gray-300">No arenas in this category yet</h3>
                <p className="text-xs text-gray-500 mt-1">Be the first to challenge the world on this topic!</p>
              </div>
            )}
          </div>
        )}

        {/* ARENA DETAIL TAB */}
        {activeTab === 'detail' && selectedArena && (
          <div className="space-y-6">
            <button
              onClick={() => setActiveTab('arenas')}
              className="text-xs text-gray-400 hover:text-white flex items-center space-x-1 transition"
            >
              <span>&larr; Back to all debates</span>
            </button>

            {/* Header Card */}
            <div className="bg-gray-900 border border-gray-800 rounded-3xl p-6 sm:p-8 relative overflow-hidden">
              <div className="flex flex-col lg:flex-row lg:items-start justify-between gap-6">
                <div className="max-w-3xl">
                  <div className="flex items-center space-x-3 text-xs mb-3">
                    <span className="font-mono text-gray-400">Arena #{selectedArena.arena_id}</span>
                    <span
                      className={`px-3 py-1 rounded-full font-semibold text-xs ${
                        selectedArena.state === 'OPEN'
                          ? 'bg-amber-500/10 text-amber-400 border border-amber-500/20'
                          : selectedArena.state === 'LOCKED'
                          ? 'bg-blue-500/10 text-blue-400 border border-blue-500/20'
                          : 'bg-emerald-500/10 text-emerald-400 border border-emerald-500/20'
                      }`}
                    >
                      {selectedArena.state}
                    </span>
                  </div>

                  <h1 className="text-2xl sm:text-3xl font-extrabold text-white leading-tight mb-4">
                    "{selectedArena.claim}"
                  </h1>

                  {selectedArena.context_urls && selectedArena.context_urls.length > 0 && (
                    <div className="flex flex-wrap items-center gap-2 text-xs text-gray-400 mt-2">
                      <span className="text-gray-500">Context references:</span>
                      {selectedArena.context_urls.map((u, idx) => (
                        <a
                          key={idx}
                          href={u}
                          target="_blank"
                          rel="noreferrer"
                          className="bg-gray-800 hover:bg-gray-700 px-2.5 py-1 rounded-md text-emerald-400 flex items-center space-x-1 transition"
                        >
                          <span>{new URL(u).hostname}</span>
                          <ExternalLink className="w-3 h-3 ml-1" />
                        </a>
                      ))}
                    </div>
                  )}
                </div>

                {/* Match Box */}
                <div className="bg-gray-950/80 border border-gray-800 rounded-2xl p-5 min-w-[280px]">
                  <div className="text-xs text-gray-400 mb-1">Total Prize Pool</div>
                  <div className="text-2xl font-extrabold text-emerald-400 mb-4">
                    {(Number(selectedArena.stake_per_side) * 2 / 1e18).toFixed(2)} GEN
                  </div>

                  <div className="space-y-2 text-xs border-t border-gray-800 pt-3">
                    <div className="flex items-center justify-between">
                      <span className="text-gray-400">PRO side:</span>
                      <span className="font-mono text-gray-200">
                        {selectedArena.pro_wallet ? `${selectedArena.pro_wallet.slice(0, 6)}...` : 'OPEN'}
                      </span>
                    </div>
                    <div className="flex items-center justify-between">
                      <span className="text-gray-400">CON side:</span>
                      <span className="font-mono text-gray-200">
                        {selectedArena.con_wallet ? `${selectedArena.con_wallet.slice(0, 6)}...` : 'OPEN'}
                      </span>
                    </div>
                  </div>

                  {selectedArena.state === 'OPEN' && account && (
                    <div className="mt-4 pt-4 border-t border-gray-800 flex gap-2">
                      {!selectedArena.pro_wallet && (
                        <button
                          onClick={() => handleJoinSide(selectedArena.arena_id, 'PRO', selectedArena.stake_per_side)}
                          className="flex-1 bg-emerald-600 hover:bg-emerald-500 text-white text-xs font-bold py-2 rounded-xl transition"
                        >
                          Join PRO
                        </button>
                      )}
                      {!selectedArena.con_wallet && (
                        <button
                          onClick={() => handleJoinSide(selectedArena.arena_id, 'CON', selectedArena.stake_per_side)}
                          className="flex-1 bg-indigo-600 hover:bg-indigo-500 text-white text-xs font-bold py-2 rounded-xl transition"
                        >
                          Join CON
                        </button>
                      )}
                    </div>
                  )}
                </div>
              </div>

              {selectedArena.verdict && (
                <div className="mt-8 pt-6 border-t border-gray-800/80">
                  <div className="bg-emerald-950/30 border border-emerald-500/30 rounded-2xl p-5">
                    <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-2 mb-3">
                      <div className="flex items-center space-x-2">
                        <Trophy className="w-5 h-5 text-emerald-400" />
                        <h4 className="font-bold text-base text-emerald-300">
                          Consensus Verdict: {selectedArena.verdict}
                        </h4>
                      </div>
                      <div className="flex items-center space-x-2 text-xs">
                        <span className="text-gray-400">Jury Confidence:</span>
                        <div className="w-24 bg-gray-800 rounded-full h-2 overflow-hidden">
                          <div
                            className="bg-emerald-400 h-full rounded-full"
                            style={{ width: `${selectedArena.confidence}%` }}
                          ></div>
                        </div>
                        <span className="font-bold text-emerald-400">{selectedArena.confidence}%</span>
                      </div>
                    </div>

                    <p className="text-sm text-gray-300 leading-relaxed italic">
                      "{selectedArena.reason}"
                    </p>
                  </div>
                </div>
              )}
            </div>

            {/* Rounds & Arguments timeline */}
            <div className="space-y-6">
              <h2 className="text-lg font-bold text-white flex items-center space-x-2">
                <Swords className="w-5 h-5 text-emerald-400" />
                <span>Debate Timeline & Submitted Evidence</span>
              </h2>

              <div className="space-y-4">
                {selectedArena.arguments && selectedArena.arguments.length > 0 ? (
                  selectedArena.arguments.map((arg, idx) => {
                    const isPro = arg.submitter.toLowerCase() === selectedArena.pro_wallet.toLowerCase();
                    return (
                      <div
                        key={idx}
                        className={`p-5 rounded-2xl border ${
                          isPro
                            ? 'bg-emerald-950/10 border-emerald-900/40 ml-0 mr-4'
                            : 'bg-indigo-950/10 border-indigo-900/40 ml-4 mr-0'
                        }`}
                      >
                        <div className="flex items-center justify-between text-xs mb-2">
                          <div className="flex items-center space-x-2">
                            <span
                              className={`px-2 py-0.5 rounded font-bold text-[10px] ${
                                isPro ? 'bg-emerald-500/20 text-emerald-400' : 'bg-indigo-500/20 text-indigo-400'
                              }`}
                            >
                              {isPro ? 'PRO DEBATER' : 'CON DEBATER'}
                            </span>
                            <span className="font-mono text-gray-400">
                              {arg.submitter.slice(0, 8)}...{arg.submitter.slice(-6)}
                            </span>
                          </div>
                          <span className="text-gray-500">Round {arg.round_number}</span>
                        </div>

                        <p className="text-sm text-gray-200 whitespace-pre-wrap leading-relaxed">
                          {arg.text}
                        </p>

                        {arg.evidence_urls && arg.evidence_urls.length > 0 && (
                          <div className="mt-3 pt-3 border-t border-gray-800/40 flex flex-wrap items-center gap-2 text-xs">
                            <span className="text-gray-500 text-[11px]">Cited Evidence URLs:</span>
                            {arg.evidence_urls.map((u, i) => (
                              <a
                                key={i}
                                href={u}
                                target="_blank"
                                rel="noreferrer"
                                className="bg-gray-800/80 hover:bg-gray-700 px-2.5 py-1 rounded text-emerald-400 flex items-center space-x-1 transition"
                              >
                                <span className="underline">{u}</span>
                                <ExternalLink className="w-3 h-3 ml-1" />
                              </a>
                            ))}
                          </div>
                        )}
                      </div>
                    );
                  })
                ) : (
                  <div className="text-center py-10 bg-gray-900/40 border border-gray-800 rounded-2xl text-xs text-gray-400">
                    No arguments submitted yet. Once both sides join, debaters submit 3 rounds of arguments.
                  </div>
                )}
              </div>
            </div>

            {/* Submission Form */}
            {selectedArena.state === 'LOCKED' && account && (
              <div className="bg-gray-900 border border-gray-800 rounded-2xl p-6">
                <h3 className="text-base font-bold text-white mb-2">Submit Round {selectedArena.current_round} Argument</h3>
                <p className="text-xs text-gray-400 mb-4">
                  Include clear reasoning and URL evidence. AI validators will fetch and read the URL on-chain.
                </p>

                <form onSubmit={handleSubmitArgument} className="space-y-4">
                  <div>
                    <label className="block text-xs font-semibold text-gray-300 mb-1">Argument Text</label>
                    <textarea
                      rows={3}
                      value={argText}
                      onChange={(e) => setArgText(e.target.value)}
                      placeholder="Present your logical claim and analysis..."
                      className="w-full bg-gray-950 border border-gray-800 rounded-xl p-3 text-sm text-gray-100 focus:outline-none focus:border-emerald-500"
                      required
                    />
                  </div>

                  <div>
                    <label className="block text-xs font-semibold text-gray-300 mb-1">Evidence URL (Optional, but highly weighted by AI Jury)</label>
                    <input
                      type="url"
                      value={argUrl}
                      onChange={(e) => setArgUrl(e.target.value)}
                      placeholder="https://..."
                      className="w-full bg-gray-950 border border-gray-800 rounded-xl p-3 text-sm text-gray-100 focus:outline-none focus:border-emerald-500"
                    />
                  </div>

                  <button
                    type="submit"
                    className="bg-emerald-600 hover:bg-emerald-500 text-white text-xs font-bold px-5 py-2.5 rounded-xl transition shadow-lg shadow-emerald-600/20"
                  >
                    Submit Round Argument
                  </button>
                </form>
              </div>
            )}
          </div>
        )}

        {/* REPUTATION TAB */}
        {activeTab === 'reputation' && (
          <div className="max-w-3xl mx-auto space-y-6">
            <div>
              <h1 className="text-2xl font-extrabold text-white tracking-tight">On-Chain Debater Reputation</h1>
              <p className="text-sm text-gray-400 mt-1">
                Lookup any debater wallet to view verifiable win/loss/draw records and earned tier badges.
              </p>
            </div>

            <div className="flex gap-2">
              <input
                type="text"
                value={repAddress}
                onChange={(e) => setRepAddress(e.target.value)}
                placeholder="0x... wallet address"
                className="flex-1 bg-gray-900 border border-gray-800 rounded-xl p-3 text-sm text-gray-100 focus:outline-none focus:border-emerald-500"
              />
              <button
                onClick={() => fetchReputation(repAddress)}
                className="bg-emerald-600 hover:bg-emerald-500 text-white text-xs font-bold px-5 py-3 rounded-xl transition"
              >
                Lookup
              </button>
            </div>

            {reputation && (
              <div className="bg-gray-900 border border-gray-800 rounded-2xl p-6 space-y-6">
                <div className="flex items-center justify-between pb-4 border-b border-gray-800">
                  <div>
                    <div className="text-xs text-gray-500">Debater Wallet</div>
                    <div className="font-mono text-sm text-gray-200 mt-0.5">{reputation.wallet}</div>
                  </div>
                  <div className="text-right">
                    <div className="text-xs text-gray-500">Tier Badge</div>
                    <span className="inline-block mt-0.5 px-3 py-1 bg-gradient-to-r from-emerald-500 to-indigo-600 text-white font-extrabold text-xs rounded-full">
                      {reputation.tier}
                    </span>
                  </div>
                </div>

                <div className="grid grid-cols-4 gap-4 text-center">
                  <div className="bg-gray-950 p-4 rounded-xl border border-gray-800/80">
                    <div className="text-2xl font-black text-white">{reputation.total_matches}</div>
                    <div className="text-[11px] text-gray-400 uppercase tracking-wider mt-1">Matches</div>
                  </div>
                  <div className="bg-gray-950 p-4 rounded-xl border border-gray-800/80">
                    <div className="text-2xl font-black text-emerald-400">{reputation.wins}</div>
                    <div className="text-[11px] text-gray-400 uppercase tracking-wider mt-1">Wins</div>
                  </div>
                  <div className="bg-gray-950 p-4 rounded-xl border border-gray-800/80">
                    <div className="text-2xl font-black text-rose-400">{reputation.losses}</div>
                    <div className="text-[11px] text-gray-400 uppercase tracking-wider mt-1">Losses</div>
                  </div>
                  <div className="bg-gray-950 p-4 rounded-xl border border-gray-800/80">
                    <div className="text-2xl font-black text-indigo-400">{reputation.win_rate}%</div>
                    <div className="text-[11px] text-gray-400 uppercase tracking-wider mt-1">Win Rate</div>
                  </div>
                </div>
              </div>
            )}
          </div>
        )}

        {/* ABOUT TAB */}
        {activeTab === 'about' && (
          <div className="max-w-3xl mx-auto space-y-6">
            <h1 className="text-2xl font-extrabold text-white tracking-tight">How TruthArena Works</h1>
            <div className="prose prose-invert text-sm text-gray-300 space-y-4">
              <p>
                TruthArena is an autonomous 1v1 debate arena where opposing debaters stake GEN tokens on real-world claims. Unlike traditional smart contracts that can only process numbers, TruthArena utilizes GenLayer Intelligent Contracts to read full articles, research papers, and web evidence on-chain without oracles.
              </p>
              <h3 className="text-lg font-bold text-white mt-6">Why GenLayer is Essential</h3>
              <ul className="list-disc pl-5 space-y-2">
                <li><strong>On-Chain Web Fetching:</strong> The contract runs <code>gl.nondet.web.render</code> to parse raw text from cited URLs in real-time.</li>
                <li><strong>Subjective Consensus:</strong> An AI jury of diverse LLM validators evaluates logical validity, counter-argument effectiveness, and citation accuracy.</li>
                <li><strong>Semantic Consensus:</strong> Validators only reach consensus on the core verdict (<code>PRO_WINS</code> vs <code>CON_WINS</code>), ensuring robust convergence despite stylistic variations.</li>
              </ul>
            </div>
          </div>
        )}
      </main>

      {/* CREATE ARENA MODAL */}
      {showCreateModal && (
        <div className="fixed inset-0 bg-black/80 backdrop-blur-sm flex items-center justify-center p-4 z-50">
          <div className="bg-gray-900 border border-gray-800 rounded-3xl max-w-lg w-full p-6 sm:p-8 space-y-6">
            <div className="flex items-center justify-between">
              <h3 className="text-lg font-bold text-white">Create 1v1 Debate Arena</h3>
              <button
                onClick={() => setShowCreateModal(false)}
                className="text-gray-400 hover:text-white text-sm"
              >
                &times;
              </button>
            </div>

            <form onSubmit={handleCreateArena} className="space-y-4">
              <div>
                <label className="block text-xs font-semibold text-gray-300 mb-1">Claim under debate (Max 400 chars)</label>
                <textarea
                  rows={3}
                  value={createClaim}
                  onChange={(e) => setCreateClaim(e.target.value)}
                  placeholder="e.g. Commercial nuclear fusion will be net-positive before 2035."
                  className="w-full bg-gray-950 border border-gray-800 rounded-xl p-3 text-sm text-gray-100 focus:outline-none focus:border-emerald-500"
                  required
                />
              </div>

              <div>
                <label className="block text-xs font-semibold text-gray-300 mb-1">Context URL (Optional)</label>
                <input
                  type="url"
                  value={createContextUrl}
                  onChange={(e) => setCreateContextUrl(e.target.value)}
                  placeholder="https://en.wikipedia.org/wiki/..."
                  className="w-full bg-gray-950 border border-gray-800 rounded-xl p-3 text-sm text-gray-100 focus:outline-none focus:border-emerald-500"
                />
              </div>

              <div className="grid grid-cols-2 gap-4">
                <div>
                  <label className="block text-xs font-semibold text-gray-300 mb-1">Your Side</label>
                  <select
                    value={createSide}
                    onChange={(e: any) => setCreateSide(e.target.value)}
                    className="w-full bg-gray-950 border border-gray-800 rounded-xl p-3 text-sm text-gray-100 focus:outline-none focus:border-emerald-500"
                  >
                    <option value="PRO">PRO (Claim is TRUE)</option>
                    <option value="CON">CON (Claim is FALSE)</option>
                  </select>
                </div>

                <div>
                  <label className="block text-xs font-semibold text-gray-300 mb-1">Stake (GEN)</label>
                  <input
                    type="number"
                    step="0.01"
                    min="0.01"
                    value={createStake}
                    onChange={(e) => setCreateStake(e.target.value)}
                    className="w-full bg-gray-950 border border-gray-800 rounded-xl p-3 text-sm text-gray-100 focus:outline-none focus:border-emerald-500"
                    required
                  />
                </div>
              </div>

              <div className="pt-4 flex gap-3">
                <button
                  type="button"
                  onClick={() => setShowCreateModal(false)}
                  className="flex-1 bg-gray-800 hover:bg-gray-700 text-white text-xs font-semibold py-3 rounded-xl transition"
                >
                  Cancel
                </button>
                <button
                  type="submit"
                  disabled={consensusWaiting}
                  className="flex-1 bg-emerald-600 hover:bg-emerald-500 text-white text-xs font-bold py-3 rounded-xl transition shadow-lg shadow-emerald-600/20"
                >
                  {consensusWaiting ? 'Deploying...' : 'Lock Stake & Open Arena'}
                </button>
              </div>
            </form>
          </div>
        </div>
      )}
    </div>
  );
}
