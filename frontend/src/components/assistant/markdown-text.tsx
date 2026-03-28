import { StreamdownTextPrimitive } from '@assistant-ui/react-streamdown'
import { code } from '@streamdown/code'

const streamdownPlugins = { code }

export function MarkdownText() {
  return <StreamdownTextPrimitive plugins={streamdownPlugins} />
}
