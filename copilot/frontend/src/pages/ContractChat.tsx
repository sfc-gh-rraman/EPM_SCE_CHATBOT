import { Chat } from '../components/Chat'

export function ContractChat() {
  return (
    <div className="h-full flex flex-col">
      <header className="px-6 py-4 border-b border-slate-200 bg-white">
        <h1 className="text-xl font-semibold text-slate-900">
          SCE EPM Contract Assistant
        </h1>
        <p className="text-sm text-slate-500">
          Conversational access to PPA / RA / Tolling contracts and amendments,
          powered by Snowflake Cortex Agents.
        </p>
      </header>
      <div className="flex-1 overflow-hidden">
        <Chat />
      </div>
    </div>
  )
}
