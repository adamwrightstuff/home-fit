import ResultsClient from './results-client'

export default async function ResultsPage({
  searchParams,
}: {
  searchParams: Record<string, string | string[] | undefined>
}) {
  return <ResultsClient initialSearchParams={searchParams} />
}

