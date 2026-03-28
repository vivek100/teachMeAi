export type LectureNoteSection = {
  id: string
  title: string
  bullets: string[]
}

export const lectureNotes: LectureNoteSection[] = [
  {
    id: 'framing',
    title: 'Lecture framing',
    bullets: [
      'Goal: teach the progression from tokenization to embeddings to self-attention.',
      'Keep visuals simple enough to appear in under a second.',
      'Prefer one strong artifact per concept instead of drawing everything at once.',
    ],
  },
  {
    id: 'tokenization',
    title: 'Tokenization segment',
    bullets: [
      'Explain how text is broken into tokens and subwords.',
      'Use a token grid artifact when the lecturer gives a concrete sentence example.',
      'Highlight token IDs only if the transcript explicitly mentions vocab or IDs.',
    ],
  },
  {
    id: 'embeddings',
    title: 'Embedding segment',
    bullets: [
      'Move from discrete token IDs to continuous vectors.',
      'Use spatial metaphors carefully: similar words cluster, but dimensions are abstract.',
      'Prefer the embedding-space artifact when the lecturer contrasts semantics.',
    ],
  },
  {
    id: 'attention',
    title: 'Self-attention segment',
    bullets: [
      'Introduce queries, keys, and values with a matrix-style visual.',
      'Render the attention matrix when the lecturer talks about token-to-token influence.',
      'Avoid over-annotating unless the lecturer pauses to inspect relationships.',
    ],
  },
]
