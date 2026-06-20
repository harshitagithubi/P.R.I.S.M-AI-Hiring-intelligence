const TERMS = [
  "ranking",
  "retrieval",
  "recommendation",
  "recommendations",
  "recommender",
  "embedding",
  "embeddings",
  "vector search",
  "vector database",
  "faiss",
  "pinecone",
  "qdrant",
  "weaviate",
  "evaluation",
  "ndcg",
  "mrr",
  "xgboost",
  "lightgbm",
  "python",
  "spark",
  "airflow"
];

export function EvidenceHighlight({ text }: { text: string }) {
  const escaped = TERMS.map((term) => term.replace(/[.*+?^${}()|[\]\\]/g, "\\$&"));
  const pattern = new RegExp(`\\b(${escaped.join("|")})\\b`, "gi");
  const parts = text.split(pattern);
  return (
    <>
      {parts.map((part, index) => {
        const isMatch = TERMS.some((term) => term.toLowerCase() === part.toLowerCase());
        return isMatch ? (
          <span key={`${part}-${index}`} className="rounded bg-prism-cyan/15 px-1 text-prism-cyan">{part}</span>
        ) : (
          <span key={`${part}-${index}`}>{part}</span>
        );
      })}
    </>
  );
}
