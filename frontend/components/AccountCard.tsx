import type { ConnectedAccount } from '@/lib/api'

interface AccountCardProps {
  account: ConnectedAccount
  onDisconnect: (accountId: number) => void
}

export default function AccountCard({ account, onDisconnect }: AccountCardProps) {
  const isFacebook = account.platform === 'facebook'

  return (
    <div className="flex items-center justify-between p-4 border border-gray-200 rounded-lg hover:border-gray-300 transition-colors">
      <div className="flex items-center gap-4">
        <div
          className={`w-12 h-12 rounded-full flex items-center justify-center ${
            isFacebook
              ? 'bg-blue-600'
              : 'bg-gradient-to-r from-purple-500 to-pink-500'
          }`}
        >
          <span className="text-white font-bold text-xl">
            {isFacebook ? 'f' : 'i'}
          </span>
        </div>
        <div>
          <p className="font-semibold text-gray-800">
            {account.platform_username || account.page_name || 'Unknown'}
          </p>
          <p className="text-sm text-gray-500 capitalize">
            {account.platform}
          </p>
          {account.page_name && account.platform_username && (
            <p className="text-xs text-gray-400">
              Page: {account.page_name}
            </p>
          )}
        </div>
      </div>
      <button
        onClick={() => onDisconnect(account.id)}
        className="px-4 py-2 text-red-600 hover:bg-red-50 rounded-lg transition-colors text-sm font-medium"
      >
        Disconnect
      </button>
    </div>
  )
}
