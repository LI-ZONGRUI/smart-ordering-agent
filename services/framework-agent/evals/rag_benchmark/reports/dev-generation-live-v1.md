# RAG Retrieval + Evidence-first Grounding Benchmark v1

```json
{
  "benchmarkVersion": 1,
  "validatorVersion": 1,
  "mode": "live-generation",
  "split": "dev",
  "casesInScope": 30,
  "splitCounts": {
    "dev": 30,
    "holdout": 10
  },
  "datasetManifestHash": "9917b50dd645dd0741539f9b1411a65764b9b67cc8ea823d583f207eb0907b62",
  "knowledgeSourceHash": "f341c287c97056b4766fd514532de31fc8a2b5cd0a3e76641283192fcd04f0a6",
  "productionRagFingerprint": "3f06ef7a9326961fbc62441d85de2cd42a8a39cee4ad42ef1a41d2b505bb9918",
  "embeddingModel": "qwen3.7-text-embedding-flash",
  "embeddingDimension": 512,
  "topK": 3,
  "retrievalMeasurement": "real-query-embedding-against-audited-local-export",
  "generationMeasurement": "Qwen-with-frozen-local-live-facts",
  "indexSnapshotHash": "56c01e8361be536bf8e4dac62179d682b149ce36f0bb7acf7abd52672bc8b678",
  "indexOriginAttestation": "user-audited-export-not-cryptographic-provider-proof"
}
```

Scores describe this benchmark and fixture scope, not production accuracy.

REVIEW is not PASS and remains in applicable denominators.

## Metrics

```json
{
  "metrics": {
    "retrieval_hit_at_3": {
      "applicable": 21,
      "pass": 20,
      "machineDetectedFail": 0,
      "review": 1,
      "conservativeAutomaticPassRate": 0.9523809523809523,
      "determinateCheckCoverage": 0.9523809523809523,
      "value": 0.9523809523809523,
      "valueMeaning": "conservative-score"
    },
    "recall_at_3": {
      "applicable": 21,
      "pass": 19,
      "machineDetectedFail": 1,
      "review": 1,
      "conservativeAutomaticPassRate": 0.9047619047619048,
      "determinateCheckCoverage": 0.9523809523809523,
      "value": 0.9285714285714286,
      "valueMeaning": "conservative-score"
    },
    "evidence_relevance": {
      "applicable": 20,
      "pass": 12,
      "machineDetectedFail": 7,
      "review": 1,
      "conservativeAutomaticPassRate": 0.6,
      "determinateCheckCoverage": 0.95,
      "value": 0.6,
      "valueMeaning": "conservative-score"
    },
    "correct_knowledge_id_retrieval": {
      "applicable": 30,
      "pass": 29,
      "machineDetectedFail": 0,
      "review": 1,
      "conservativeAutomaticPassRate": 0.9666666666666667,
      "determinateCheckCoverage": 0.9666666666666667,
      "value": 0.9666666666666667,
      "valueMeaning": "conservative-score"
    },
    "answerability_accuracy": {
      "applicable": 30,
      "pass": 29,
      "machineDetectedFail": 0,
      "review": 1,
      "conservativeAutomaticPassRate": 0.9666666666666667,
      "determinateCheckCoverage": 0.9666666666666667,
      "value": 0.9666666666666667,
      "valueMeaning": "conservative-score"
    },
    "correct_rejection_rate": {
      "applicable": 10,
      "pass": 10,
      "machineDetectedFail": 0,
      "review": 0,
      "conservativeAutomaticPassRate": 1.0,
      "determinateCheckCoverage": 1.0,
      "value": 1.0,
      "valueMeaning": "conservative-score"
    },
    "grounding_accuracy": {
      "applicable": 30,
      "pass": 29,
      "machineDetectedFail": 0,
      "review": 1,
      "conservativeAutomaticPassRate": 0.9666666666666667,
      "determinateCheckCoverage": 0.9666666666666667,
      "value": 0.9666666666666667,
      "valueMeaning": "conservative-score"
    },
    "evidence_attribution_accuracy": {
      "applicable": 30,
      "pass": 29,
      "machineDetectedFail": 0,
      "review": 1,
      "conservativeAutomaticPassRate": 0.9666666666666667,
      "determinateCheckCoverage": 0.9666666666666667,
      "value": 0.9666666666666667,
      "valueMeaning": "conservative-score"
    },
    "used_knowledge_ids_validity": {
      "applicable": 30,
      "pass": 29,
      "machineDetectedFail": 0,
      "review": 1,
      "conservativeAutomaticPassRate": 0.9666666666666667,
      "determinateCheckCoverage": 0.9666666666666667,
      "value": 0.9666666666666667,
      "valueMeaning": "conservative-score"
    },
    "context_answerability_accuracy": {
      "applicable": 30,
      "pass": 28,
      "machineDetectedFail": 1,
      "review": 1,
      "conservativeAutomaticPassRate": 0.9333333333333333,
      "determinateCheckCoverage": 0.9666666666666667,
      "value": 0.9333333333333333,
      "valueMeaning": "conservative-score"
    },
    "unsupported_answer_rate": {
      "applicable": 10,
      "pass": 10,
      "machineDetectedFail": 0,
      "review": 0,
      "conservativeAutomaticPassRate": 1.0,
      "determinateCheckCoverage": 1.0,
      "value": 0.0,
      "valueMeaning": "observed-error-lower-bound"
    },
    "unsupported_claim_rate": {
      "applicable": 30,
      "pass": 29,
      "machineDetectedFail": 0,
      "review": 1,
      "conservativeAutomaticPassRate": 0.9666666666666667,
      "determinateCheckCoverage": 0.9666666666666667,
      "value": 0.0,
      "valueMeaning": "observed-error-lower-bound"
    }
  },
  "casesRequiringReview": 1,
  "failureDistribution": {
    "EVIDENCE_SELECTION_MISS": 7
  },
  "reviewDistribution": {
    "GENERATION_NOT_OBSERVED": 1,
    "RETRIEVAL_NOT_OBSERVED": 1,
    "RETRIEVAL_NOT_SCORABLE": 1
  }
}
```

## Safe case diagnostics

```json
{
  "id": "rag_dev_direct_fact_001",
  "category": "direct_fact",
  "split": "dev",
  "retrievalRanks": [
    {
      "rank": 1,
      "knowledgeId": "dish-1-ingredients",
      "similarity": 0.879906
    },
    {
      "rank": 2,
      "knowledgeId": "dish-1-description",
      "similarity": 0.832545
    },
    {
      "rank": 3,
      "knowledgeId": "dish-1-taste",
      "similarity": 0.77145
    }
  ],
  "usedKnowledgeIds": [
    "dish-1-ingredients"
  ],
  "metrics": {
    "retrieval_hit_at_3": "PASS",
    "recall_at_3": "PASS",
    "evidence_relevance": "PASS",
    "correct_knowledge_id_retrieval": "PASS",
    "answerability_accuracy": "PASS",
    "correct_rejection_rate": null,
    "grounding_accuracy": "PASS",
    "evidence_attribution_accuracy": "PASS",
    "used_knowledge_ids_validity": "PASS",
    "context_answerability_accuracy": "PASS",
    "unsupported_answer_rate": null,
    "unsupported_claim_rate": "PASS"
  },
  "values": {
    "retrieval_hit_at_3": true,
    "recall_at_3": 1.0,
    "evidence_relevance": true,
    "correct_knowledge_id_retrieval": true,
    "answerability_accuracy": true,
    "correct_rejection_rate": null,
    "grounding_accuracy": true,
    "evidence_attribution_accuracy": true,
    "used_knowledge_ids_validity": true,
    "context_answerability_accuracy": true,
    "unsupported_answer_rate": null,
    "unsupported_claim_rate": false
  },
  "failureCodes": [],
  "reviewReasons": [],
  "contextSupported": true
}
```

```json
{
  "id": "rag_dev_direct_fact_002",
  "category": "direct_fact",
  "split": "dev",
  "retrievalRanks": [
    {
      "rank": 1,
      "knowledgeId": "dish-2-description",
      "similarity": 0.963654
    },
    {
      "rank": 2,
      "knowledgeId": "dish-2-taste",
      "similarity": 0.834477
    },
    {
      "rank": 3,
      "knowledgeId": "dish-2-ingredients",
      "similarity": 0.779981
    }
  ],
  "usedKnowledgeIds": [
    "dish-2-description"
  ],
  "metrics": {
    "retrieval_hit_at_3": "PASS",
    "recall_at_3": "PASS",
    "evidence_relevance": "PASS",
    "correct_knowledge_id_retrieval": "PASS",
    "answerability_accuracy": "PASS",
    "correct_rejection_rate": null,
    "grounding_accuracy": "PASS",
    "evidence_attribution_accuracy": "PASS",
    "used_knowledge_ids_validity": "PASS",
    "context_answerability_accuracy": "PASS",
    "unsupported_answer_rate": null,
    "unsupported_claim_rate": "PASS"
  },
  "values": {
    "retrieval_hit_at_3": true,
    "recall_at_3": 1.0,
    "evidence_relevance": true,
    "correct_knowledge_id_retrieval": true,
    "answerability_accuracy": true,
    "correct_rejection_rate": null,
    "grounding_accuracy": true,
    "evidence_attribution_accuracy": true,
    "used_knowledge_ids_validity": true,
    "context_answerability_accuracy": true,
    "unsupported_answer_rate": null,
    "unsupported_claim_rate": false
  },
  "failureCodes": [],
  "reviewReasons": [],
  "contextSupported": true
}
```

```json
{
  "id": "rag_dev_direct_fact_003",
  "category": "direct_fact",
  "split": "dev",
  "retrievalRanks": [
    {
      "rank": 1,
      "knowledgeId": "dish-3-description",
      "similarity": 0.865
    },
    {
      "rank": 2,
      "knowledgeId": "dish-3-ingredients",
      "similarity": 0.753777
    },
    {
      "rank": 3,
      "knowledgeId": "dish-3-taste",
      "similarity": 0.696599
    }
  ],
  "usedKnowledgeIds": [
    "dish-3-description",
    "dish-3-ingredients"
  ],
  "metrics": {
    "retrieval_hit_at_3": "PASS",
    "recall_at_3": "PASS",
    "evidence_relevance": "PASS",
    "correct_knowledge_id_retrieval": "PASS",
    "answerability_accuracy": "PASS",
    "correct_rejection_rate": null,
    "grounding_accuracy": "PASS",
    "evidence_attribution_accuracy": "PASS",
    "used_knowledge_ids_validity": "PASS",
    "context_answerability_accuracy": "PASS",
    "unsupported_answer_rate": null,
    "unsupported_claim_rate": "PASS"
  },
  "values": {
    "retrieval_hit_at_3": true,
    "recall_at_3": 1.0,
    "evidence_relevance": true,
    "correct_knowledge_id_retrieval": true,
    "answerability_accuracy": true,
    "correct_rejection_rate": null,
    "grounding_accuracy": true,
    "evidence_attribution_accuracy": true,
    "used_knowledge_ids_validity": true,
    "context_answerability_accuracy": true,
    "unsupported_answer_rate": null,
    "unsupported_claim_rate": false
  },
  "failureCodes": [],
  "reviewReasons": [],
  "contextSupported": true
}
```

```json
{
  "id": "rag_dev_direct_fact_004",
  "category": "direct_fact",
  "split": "dev",
  "retrievalRanks": [
    {
      "rank": 1,
      "knowledgeId": "dish-4-ingredients",
      "similarity": 0.903571
    },
    {
      "rank": 2,
      "knowledgeId": "dish-4-taste",
      "similarity": 0.671555
    },
    {
      "rank": 3,
      "knowledgeId": "dish-7-ingredients",
      "similarity": 0.591097
    }
  ],
  "usedKnowledgeIds": [
    "dish-4-ingredients"
  ],
  "metrics": {
    "retrieval_hit_at_3": "PASS",
    "recall_at_3": "PASS",
    "evidence_relevance": "PASS",
    "correct_knowledge_id_retrieval": "PASS",
    "answerability_accuracy": "PASS",
    "correct_rejection_rate": null,
    "grounding_accuracy": "PASS",
    "evidence_attribution_accuracy": "PASS",
    "used_knowledge_ids_validity": "PASS",
    "context_answerability_accuracy": "PASS",
    "unsupported_answer_rate": null,
    "unsupported_claim_rate": "PASS"
  },
  "values": {
    "retrieval_hit_at_3": true,
    "recall_at_3": 1.0,
    "evidence_relevance": true,
    "correct_knowledge_id_retrieval": true,
    "answerability_accuracy": true,
    "correct_rejection_rate": null,
    "grounding_accuracy": true,
    "evidence_attribution_accuracy": true,
    "used_knowledge_ids_validity": true,
    "context_answerability_accuracy": true,
    "unsupported_answer_rate": null,
    "unsupported_claim_rate": false
  },
  "failureCodes": [],
  "reviewReasons": [],
  "contextSupported": true
}
```

```json
{
  "id": "rag_dev_direct_fact_005",
  "category": "direct_fact",
  "split": "dev",
  "retrievalRanks": [
    {
      "rank": 1,
      "knowledgeId": "dish-7-description",
      "similarity": 0.833113
    },
    {
      "rank": 2,
      "knowledgeId": "dish-7-taste",
      "similarity": 0.820289
    },
    {
      "rank": 3,
      "knowledgeId": "dish-7-ingredients",
      "similarity": 0.792504
    }
  ],
  "usedKnowledgeIds": [
    "dish-7-description",
    "dish-7-taste",
    "dish-7-ingredients"
  ],
  "metrics": {
    "retrieval_hit_at_3": "PASS",
    "recall_at_3": "PASS",
    "evidence_relevance": "FAIL",
    "correct_knowledge_id_retrieval": "PASS",
    "answerability_accuracy": "PASS",
    "correct_rejection_rate": null,
    "grounding_accuracy": "PASS",
    "evidence_attribution_accuracy": "PASS",
    "used_knowledge_ids_validity": "PASS",
    "context_answerability_accuracy": "PASS",
    "unsupported_answer_rate": null,
    "unsupported_claim_rate": "PASS"
  },
  "values": {
    "retrieval_hit_at_3": true,
    "recall_at_3": 1.0,
    "evidence_relevance": false,
    "correct_knowledge_id_retrieval": true,
    "answerability_accuracy": true,
    "correct_rejection_rate": null,
    "grounding_accuracy": true,
    "evidence_attribution_accuracy": true,
    "used_knowledge_ids_validity": true,
    "context_answerability_accuracy": true,
    "unsupported_answer_rate": null,
    "unsupported_claim_rate": false
  },
  "failureCodes": [
    "EVIDENCE_SELECTION_MISS"
  ],
  "reviewReasons": [],
  "contextSupported": true
}
```

```json
{
  "id": "rag_dev_direct_fact_006",
  "category": "direct_fact",
  "split": "dev",
  "retrievalRanks": [
    {
      "rank": 1,
      "knowledgeId": "restaurant-spicy-level-definitions",
      "similarity": 0.845742
    },
    {
      "rank": 2,
      "knowledgeId": "dish-8-taste",
      "similarity": 0.399443
    },
    {
      "rank": 3,
      "knowledgeId": "dish-2-taste",
      "similarity": 0.39492
    }
  ],
  "usedKnowledgeIds": [
    "restaurant-spicy-level-definitions"
  ],
  "metrics": {
    "retrieval_hit_at_3": "PASS",
    "recall_at_3": "PASS",
    "evidence_relevance": "PASS",
    "correct_knowledge_id_retrieval": "PASS",
    "answerability_accuracy": "PASS",
    "correct_rejection_rate": null,
    "grounding_accuracy": "PASS",
    "evidence_attribution_accuracy": "PASS",
    "used_knowledge_ids_validity": "PASS",
    "context_answerability_accuracy": "PASS",
    "unsupported_answer_rate": null,
    "unsupported_claim_rate": "PASS"
  },
  "values": {
    "retrieval_hit_at_3": true,
    "recall_at_3": 1.0,
    "evidence_relevance": true,
    "correct_knowledge_id_retrieval": true,
    "answerability_accuracy": true,
    "correct_rejection_rate": null,
    "grounding_accuracy": true,
    "evidence_attribution_accuracy": true,
    "used_knowledge_ids_validity": true,
    "context_answerability_accuracy": true,
    "unsupported_answer_rate": null,
    "unsupported_claim_rate": false
  },
  "failureCodes": [],
  "reviewReasons": [],
  "contextSupported": true
}
```

```json
{
  "id": "rag_dev_paraphrase_001",
  "category": "paraphrase",
  "split": "dev",
  "retrievalRanks": [
    {
      "rank": 1,
      "knowledgeId": "dish-1-taste",
      "similarity": 0.83622
    },
    {
      "rank": 2,
      "knowledgeId": "dish-1-description",
      "similarity": 0.651354
    },
    {
      "rank": 3,
      "knowledgeId": "dish-5-description",
      "similarity": 0.610474
    }
  ],
  "usedKnowledgeIds": [
    "dish-1-taste",
    "dish-1-description"
  ],
  "metrics": {
    "retrieval_hit_at_3": "PASS",
    "recall_at_3": "PASS",
    "evidence_relevance": "FAIL",
    "correct_knowledge_id_retrieval": "PASS",
    "answerability_accuracy": "PASS",
    "correct_rejection_rate": null,
    "grounding_accuracy": "PASS",
    "evidence_attribution_accuracy": "PASS",
    "used_knowledge_ids_validity": "PASS",
    "context_answerability_accuracy": "PASS",
    "unsupported_answer_rate": null,
    "unsupported_claim_rate": "PASS"
  },
  "values": {
    "retrieval_hit_at_3": true,
    "recall_at_3": 1.0,
    "evidence_relevance": false,
    "correct_knowledge_id_retrieval": true,
    "answerability_accuracy": true,
    "correct_rejection_rate": null,
    "grounding_accuracy": true,
    "evidence_attribution_accuracy": true,
    "used_knowledge_ids_validity": true,
    "context_answerability_accuracy": true,
    "unsupported_answer_rate": null,
    "unsupported_claim_rate": false
  },
  "failureCodes": [
    "EVIDENCE_SELECTION_MISS"
  ],
  "reviewReasons": [],
  "contextSupported": true
}
```

```json
{
  "id": "rag_dev_paraphrase_002",
  "category": "paraphrase",
  "split": "dev",
  "retrievalRanks": [
    {
      "rank": 1,
      "knowledgeId": "dish-4-taste",
      "similarity": 0.795444
    },
    {
      "rank": 2,
      "knowledgeId": "dish-4-ingredients",
      "similarity": 0.635645
    },
    {
      "rank": 3,
      "knowledgeId": "dish-8-taste",
      "similarity": 0.475114
    }
  ],
  "usedKnowledgeIds": [
    "dish-4-taste"
  ],
  "metrics": {
    "retrieval_hit_at_3": "PASS",
    "recall_at_3": "PASS",
    "evidence_relevance": "PASS",
    "correct_knowledge_id_retrieval": "PASS",
    "answerability_accuracy": "PASS",
    "correct_rejection_rate": null,
    "grounding_accuracy": "PASS",
    "evidence_attribution_accuracy": "PASS",
    "used_knowledge_ids_validity": "PASS",
    "context_answerability_accuracy": "PASS",
    "unsupported_answer_rate": null,
    "unsupported_claim_rate": "PASS"
  },
  "values": {
    "retrieval_hit_at_3": true,
    "recall_at_3": 1.0,
    "evidence_relevance": true,
    "correct_knowledge_id_retrieval": true,
    "answerability_accuracy": true,
    "correct_rejection_rate": null,
    "grounding_accuracy": true,
    "evidence_attribution_accuracy": true,
    "used_knowledge_ids_validity": true,
    "context_answerability_accuracy": true,
    "unsupported_answer_rate": null,
    "unsupported_claim_rate": false
  },
  "failureCodes": [],
  "reviewReasons": [],
  "contextSupported": true
}
```

```json
{
  "id": "rag_dev_paraphrase_003",
  "category": "paraphrase",
  "split": "dev",
  "retrievalRanks": [
    {
      "rank": 1,
      "knowledgeId": "dish-7-taste",
      "similarity": 0.806156
    },
    {
      "rank": 2,
      "knowledgeId": "dish-7-description",
      "similarity": 0.711036
    },
    {
      "rank": 3,
      "knowledgeId": "dish-7-ingredients",
      "similarity": 0.637087
    }
  ],
  "usedKnowledgeIds": [
    "dish-7-taste",
    "dish-7-description"
  ],
  "metrics": {
    "retrieval_hit_at_3": "PASS",
    "recall_at_3": "PASS",
    "evidence_relevance": "FAIL",
    "correct_knowledge_id_retrieval": "PASS",
    "answerability_accuracy": "PASS",
    "correct_rejection_rate": null,
    "grounding_accuracy": "PASS",
    "evidence_attribution_accuracy": "PASS",
    "used_knowledge_ids_validity": "PASS",
    "context_answerability_accuracy": "PASS",
    "unsupported_answer_rate": null,
    "unsupported_claim_rate": "PASS"
  },
  "values": {
    "retrieval_hit_at_3": true,
    "recall_at_3": 1.0,
    "evidence_relevance": false,
    "correct_knowledge_id_retrieval": true,
    "answerability_accuracy": true,
    "correct_rejection_rate": null,
    "grounding_accuracy": true,
    "evidence_attribution_accuracy": true,
    "used_knowledge_ids_validity": true,
    "context_answerability_accuracy": true,
    "unsupported_answer_rate": null,
    "unsupported_claim_rate": false
  },
  "failureCodes": [
    "EVIDENCE_SELECTION_MISS"
  ],
  "reviewReasons": [],
  "contextSupported": true
}
```

```json
{
  "id": "rag_dev_paraphrase_004",
  "category": "paraphrase",
  "split": "dev",
  "retrievalRanks": [
    {
      "rank": 1,
      "knowledgeId": "dish-2-taste",
      "similarity": 0.750724
    },
    {
      "rank": 2,
      "knowledgeId": "dish-2-description",
      "similarity": 0.618726
    },
    {
      "rank": 3,
      "knowledgeId": "dish-8-taste",
      "similarity": 0.586053
    }
  ],
  "usedKnowledgeIds": [
    "dish-2-taste",
    "dish-2-description"
  ],
  "metrics": {
    "retrieval_hit_at_3": "PASS",
    "recall_at_3": "PASS",
    "evidence_relevance": "FAIL",
    "correct_knowledge_id_retrieval": "PASS",
    "answerability_accuracy": "PASS",
    "correct_rejection_rate": null,
    "grounding_accuracy": "PASS",
    "evidence_attribution_accuracy": "PASS",
    "used_knowledge_ids_validity": "PASS",
    "context_answerability_accuracy": "PASS",
    "unsupported_answer_rate": null,
    "unsupported_claim_rate": "PASS"
  },
  "values": {
    "retrieval_hit_at_3": true,
    "recall_at_3": 1.0,
    "evidence_relevance": false,
    "correct_knowledge_id_retrieval": true,
    "answerability_accuracy": true,
    "correct_rejection_rate": null,
    "grounding_accuracy": true,
    "evidence_attribution_accuracy": true,
    "used_knowledge_ids_validity": true,
    "context_answerability_accuracy": true,
    "unsupported_answer_rate": null,
    "unsupported_claim_rate": false
  },
  "failureCodes": [
    "EVIDENCE_SELECTION_MISS"
  ],
  "reviewReasons": [],
  "contextSupported": true
}
```

```json
{
  "id": "rag_dev_paraphrase_005",
  "category": "paraphrase",
  "split": "dev",
  "retrievalRanks": [],
  "usedKnowledgeIds": [],
  "metrics": {
    "retrieval_hit_at_3": "REVIEW",
    "recall_at_3": "REVIEW",
    "evidence_relevance": "REVIEW",
    "correct_knowledge_id_retrieval": "REVIEW",
    "answerability_accuracy": "REVIEW",
    "correct_rejection_rate": null,
    "grounding_accuracy": "REVIEW",
    "evidence_attribution_accuracy": "REVIEW",
    "used_knowledge_ids_validity": "REVIEW",
    "context_answerability_accuracy": "REVIEW",
    "unsupported_answer_rate": null,
    "unsupported_claim_rate": "REVIEW"
  },
  "values": {
    "retrieval_hit_at_3": false,
    "recall_at_3": false,
    "evidence_relevance": false,
    "correct_knowledge_id_retrieval": false,
    "answerability_accuracy": false,
    "correct_rejection_rate": null,
    "grounding_accuracy": false,
    "evidence_attribution_accuracy": false,
    "used_knowledge_ids_validity": false,
    "context_answerability_accuracy": false,
    "unsupported_answer_rate": null,
    "unsupported_claim_rate": null
  },
  "failureCodes": [],
  "reviewReasons": [
    "GENERATION_NOT_OBSERVED",
    "RETRIEVAL_NOT_OBSERVED",
    "RETRIEVAL_NOT_SCORABLE"
  ],
  "contextSupported": null
}
```

```json
{
  "id": "rag_dev_multi_evidence_001",
  "category": "multi_evidence",
  "split": "dev",
  "retrievalRanks": [
    {
      "rank": 1,
      "knowledgeId": "dish-1-ingredients",
      "similarity": 0.798815
    },
    {
      "rank": 2,
      "knowledgeId": "dish-1-description",
      "similarity": 0.759269
    },
    {
      "rank": 3,
      "knowledgeId": "dish-5-ingredients",
      "similarity": 0.745766
    }
  ],
  "usedKnowledgeIds": [
    "dish-1-description",
    "dish-1-ingredients"
  ],
  "metrics": {
    "retrieval_hit_at_3": "PASS",
    "recall_at_3": "FAIL",
    "evidence_relevance": "FAIL",
    "correct_knowledge_id_retrieval": "PASS",
    "answerability_accuracy": "PASS",
    "correct_rejection_rate": null,
    "grounding_accuracy": "PASS",
    "evidence_attribution_accuracy": "PASS",
    "used_knowledge_ids_validity": "PASS",
    "context_answerability_accuracy": "FAIL",
    "unsupported_answer_rate": null,
    "unsupported_claim_rate": "PASS"
  },
  "values": {
    "retrieval_hit_at_3": true,
    "recall_at_3": 0.5,
    "evidence_relevance": false,
    "correct_knowledge_id_retrieval": true,
    "answerability_accuracy": true,
    "correct_rejection_rate": null,
    "grounding_accuracy": true,
    "evidence_attribution_accuracy": true,
    "used_knowledge_ids_validity": true,
    "context_answerability_accuracy": false,
    "unsupported_answer_rate": null,
    "unsupported_claim_rate": false
  },
  "failureCodes": [
    "EVIDENCE_SELECTION_MISS"
  ],
  "reviewReasons": [],
  "contextSupported": false
}
```

```json
{
  "id": "rag_dev_multi_evidence_002",
  "category": "multi_evidence",
  "split": "dev",
  "retrievalRanks": [
    {
      "rank": 1,
      "knowledgeId": "dish-3-description",
      "similarity": 0.805374
    },
    {
      "rank": 2,
      "knowledgeId": "dish-3-ingredients",
      "similarity": 0.738079
    },
    {
      "rank": 3,
      "knowledgeId": "dish-3-taste",
      "similarity": 0.719897
    }
  ],
  "usedKnowledgeIds": [
    "dish-3-taste",
    "dish-3-description"
  ],
  "metrics": {
    "retrieval_hit_at_3": "PASS",
    "recall_at_3": "PASS",
    "evidence_relevance": "PASS",
    "correct_knowledge_id_retrieval": "PASS",
    "answerability_accuracy": "PASS",
    "correct_rejection_rate": null,
    "grounding_accuracy": "PASS",
    "evidence_attribution_accuracy": "PASS",
    "used_knowledge_ids_validity": "PASS",
    "context_answerability_accuracy": "PASS",
    "unsupported_answer_rate": null,
    "unsupported_claim_rate": "PASS"
  },
  "values": {
    "retrieval_hit_at_3": true,
    "recall_at_3": 1.0,
    "evidence_relevance": true,
    "correct_knowledge_id_retrieval": true,
    "answerability_accuracy": true,
    "correct_rejection_rate": null,
    "grounding_accuracy": true,
    "evidence_attribution_accuracy": true,
    "used_knowledge_ids_validity": true,
    "context_answerability_accuracy": true,
    "unsupported_answer_rate": null,
    "unsupported_claim_rate": false
  },
  "failureCodes": [],
  "reviewReasons": [],
  "contextSupported": true
}
```

```json
{
  "id": "rag_dev_multi_evidence_003",
  "category": "multi_evidence",
  "split": "dev",
  "retrievalRanks": [
    {
      "rank": 1,
      "knowledgeId": "dish-2-ingredients",
      "similarity": 0.777149
    },
    {
      "rank": 2,
      "knowledgeId": "dish-6-ingredients",
      "similarity": 0.769472
    },
    {
      "rank": 3,
      "knowledgeId": "dish-6-description",
      "similarity": 0.763076
    }
  ],
  "usedKnowledgeIds": [
    "dish-2-ingredients",
    "dish-6-ingredients"
  ],
  "metrics": {
    "retrieval_hit_at_3": "PASS",
    "recall_at_3": "PASS",
    "evidence_relevance": "PASS",
    "correct_knowledge_id_retrieval": "PASS",
    "answerability_accuracy": "PASS",
    "correct_rejection_rate": null,
    "grounding_accuracy": "PASS",
    "evidence_attribution_accuracy": "PASS",
    "used_knowledge_ids_validity": "PASS",
    "context_answerability_accuracy": "PASS",
    "unsupported_answer_rate": null,
    "unsupported_claim_rate": "PASS"
  },
  "values": {
    "retrieval_hit_at_3": true,
    "recall_at_3": 1.0,
    "evidence_relevance": true,
    "correct_knowledge_id_retrieval": true,
    "answerability_accuracy": true,
    "correct_rejection_rate": null,
    "grounding_accuracy": true,
    "evidence_attribution_accuracy": true,
    "used_knowledge_ids_validity": true,
    "context_answerability_accuracy": true,
    "unsupported_answer_rate": null,
    "unsupported_claim_rate": false
  },
  "failureCodes": [],
  "reviewReasons": [],
  "contextSupported": true
}
```

```json
{
  "id": "rag_dev_multi_evidence_004",
  "category": "multi_evidence",
  "split": "dev",
  "retrievalRanks": [
    {
      "rank": 1,
      "knowledgeId": "dish-4-taste",
      "similarity": 0.804719
    },
    {
      "rank": 2,
      "knowledgeId": "dish-4-ingredients",
      "similarity": 0.774969
    },
    {
      "rank": 3,
      "knowledgeId": "dish-7-ingredients",
      "similarity": 0.524342
    }
  ],
  "usedKnowledgeIds": [
    "dish-4-taste",
    "dish-4-ingredients"
  ],
  "metrics": {
    "retrieval_hit_at_3": "PASS",
    "recall_at_3": "PASS",
    "evidence_relevance": "PASS",
    "correct_knowledge_id_retrieval": "PASS",
    "answerability_accuracy": "PASS",
    "correct_rejection_rate": null,
    "grounding_accuracy": "PASS",
    "evidence_attribution_accuracy": "PASS",
    "used_knowledge_ids_validity": "PASS",
    "context_answerability_accuracy": "PASS",
    "unsupported_answer_rate": null,
    "unsupported_claim_rate": "PASS"
  },
  "values": {
    "retrieval_hit_at_3": true,
    "recall_at_3": 1.0,
    "evidence_relevance": true,
    "correct_knowledge_id_retrieval": true,
    "answerability_accuracy": true,
    "correct_rejection_rate": null,
    "grounding_accuracy": true,
    "evidence_attribution_accuracy": true,
    "used_knowledge_ids_validity": true,
    "context_answerability_accuracy": true,
    "unsupported_answer_rate": null,
    "unsupported_claim_rate": false
  },
  "failureCodes": [],
  "reviewReasons": [],
  "contextSupported": true
}
```

```json
{
  "id": "rag_dev_similar_dish_001",
  "category": "similar_dish",
  "split": "dev",
  "retrievalRanks": [
    {
      "rank": 1,
      "knowledgeId": "dish-2-description",
      "similarity": 0.810782
    },
    {
      "rank": 2,
      "knowledgeId": "dish-2-ingredients",
      "similarity": 0.790681
    },
    {
      "rank": 3,
      "knowledgeId": "dish-2-taste",
      "similarity": 0.754398
    }
  ],
  "usedKnowledgeIds": [
    "dish-2-description",
    "dish-2-ingredients",
    "dish-2-taste"
  ],
  "metrics": {
    "retrieval_hit_at_3": "PASS",
    "recall_at_3": "PASS",
    "evidence_relevance": "FAIL",
    "correct_knowledge_id_retrieval": "PASS",
    "answerability_accuracy": "PASS",
    "correct_rejection_rate": null,
    "grounding_accuracy": "PASS",
    "evidence_attribution_accuracy": "PASS",
    "used_knowledge_ids_validity": "PASS",
    "context_answerability_accuracy": "PASS",
    "unsupported_answer_rate": null,
    "unsupported_claim_rate": "PASS"
  },
  "values": {
    "retrieval_hit_at_3": true,
    "recall_at_3": 1.0,
    "evidence_relevance": false,
    "correct_knowledge_id_retrieval": true,
    "answerability_accuracy": true,
    "correct_rejection_rate": null,
    "grounding_accuracy": true,
    "evidence_attribution_accuracy": true,
    "used_knowledge_ids_validity": true,
    "context_answerability_accuracy": true,
    "unsupported_answer_rate": null,
    "unsupported_claim_rate": false
  },
  "failureCodes": [
    "EVIDENCE_SELECTION_MISS"
  ],
  "reviewReasons": [],
  "contextSupported": true
}
```

```json
{
  "id": "rag_dev_similar_dish_002",
  "category": "similar_dish",
  "split": "dev",
  "retrievalRanks": [
    {
      "rank": 1,
      "knowledgeId": "dish-7-taste",
      "similarity": 0.763644
    },
    {
      "rank": 2,
      "knowledgeId": "dish-4-taste",
      "similarity": 0.672094
    },
    {
      "rank": 3,
      "knowledgeId": "dish-7-description",
      "similarity": 0.671588
    }
  ],
  "usedKnowledgeIds": [
    "dish-7-taste",
    "dish-4-taste"
  ],
  "metrics": {
    "retrieval_hit_at_3": "PASS",
    "recall_at_3": "PASS",
    "evidence_relevance": "PASS",
    "correct_knowledge_id_retrieval": "PASS",
    "answerability_accuracy": "PASS",
    "correct_rejection_rate": null,
    "grounding_accuracy": "PASS",
    "evidence_attribution_accuracy": "PASS",
    "used_knowledge_ids_validity": "PASS",
    "context_answerability_accuracy": "PASS",
    "unsupported_answer_rate": null,
    "unsupported_claim_rate": "PASS"
  },
  "values": {
    "retrieval_hit_at_3": true,
    "recall_at_3": 1.0,
    "evidence_relevance": true,
    "correct_knowledge_id_retrieval": true,
    "answerability_accuracy": true,
    "correct_rejection_rate": null,
    "grounding_accuracy": true,
    "evidence_attribution_accuracy": true,
    "used_knowledge_ids_validity": true,
    "context_answerability_accuracy": true,
    "unsupported_answer_rate": null,
    "unsupported_claim_rate": false
  },
  "failureCodes": [],
  "reviewReasons": [],
  "contextSupported": true
}
```

```json
{
  "id": "rag_dev_similar_dish_003",
  "category": "similar_dish",
  "split": "dev",
  "retrievalRanks": [
    {
      "rank": 1,
      "knowledgeId": "dish-5-description",
      "similarity": 0.778143
    },
    {
      "rank": 2,
      "knowledgeId": "dish-1-description",
      "similarity": 0.763195
    },
    {
      "rank": 3,
      "knowledgeId": "dish-5-ingredients",
      "similarity": 0.707959
    }
  ],
  "usedKnowledgeIds": [
    "dish-1-description",
    "dish-5-description"
  ],
  "metrics": {
    "retrieval_hit_at_3": "PASS",
    "recall_at_3": "PASS",
    "evidence_relevance": "FAIL",
    "correct_knowledge_id_retrieval": "PASS",
    "answerability_accuracy": "PASS",
    "correct_rejection_rate": null,
    "grounding_accuracy": "PASS",
    "evidence_attribution_accuracy": "PASS",
    "used_knowledge_ids_validity": "PASS",
    "context_answerability_accuracy": "PASS",
    "unsupported_answer_rate": null,
    "unsupported_claim_rate": "PASS"
  },
  "values": {
    "retrieval_hit_at_3": true,
    "recall_at_3": 1.0,
    "evidence_relevance": false,
    "correct_knowledge_id_retrieval": true,
    "answerability_accuracy": true,
    "correct_rejection_rate": null,
    "grounding_accuracy": true,
    "evidence_attribution_accuracy": true,
    "used_knowledge_ids_validity": true,
    "context_answerability_accuracy": true,
    "unsupported_answer_rate": null,
    "unsupported_claim_rate": false
  },
  "failureCodes": [
    "EVIDENCE_SELECTION_MISS"
  ],
  "reviewReasons": [],
  "contextSupported": true
}
```

```json
{
  "id": "rag_dev_similar_dish_004",
  "category": "similar_dish",
  "split": "dev",
  "retrievalRanks": [
    {
      "rank": 1,
      "knowledgeId": "dish-2-description",
      "similarity": 0.811346
    },
    {
      "rank": 2,
      "knowledgeId": "dish-2-taste",
      "similarity": 0.774162
    },
    {
      "rank": 3,
      "knowledgeId": "dish-2-ingredients",
      "similarity": 0.739728
    }
  ],
  "usedKnowledgeIds": [
    "dish-2-description"
  ],
  "metrics": {
    "retrieval_hit_at_3": "PASS",
    "recall_at_3": "PASS",
    "evidence_relevance": "PASS",
    "correct_knowledge_id_retrieval": "PASS",
    "answerability_accuracy": "PASS",
    "correct_rejection_rate": null,
    "grounding_accuracy": "PASS",
    "evidence_attribution_accuracy": "PASS",
    "used_knowledge_ids_validity": "PASS",
    "context_answerability_accuracy": "PASS",
    "unsupported_answer_rate": null,
    "unsupported_claim_rate": "PASS"
  },
  "values": {
    "retrieval_hit_at_3": true,
    "recall_at_3": 1.0,
    "evidence_relevance": true,
    "correct_knowledge_id_retrieval": true,
    "answerability_accuracy": true,
    "correct_rejection_rate": null,
    "grounding_accuracy": true,
    "evidence_attribution_accuracy": true,
    "used_knowledge_ids_validity": true,
    "context_answerability_accuracy": true,
    "unsupported_answer_rate": null,
    "unsupported_claim_rate": false
  },
  "failureCodes": [],
  "reviewReasons": [],
  "contextSupported": true
}
```

```json
{
  "id": "rag_dev_unsupported_inference_001",
  "category": "unsupported_inference",
  "split": "dev",
  "retrievalRanks": [
    {
      "rank": 1,
      "knowledgeId": "dish-4-ingredients",
      "similarity": 0.605591
    },
    {
      "rank": 2,
      "knowledgeId": "dish-4-taste",
      "similarity": 0.583661
    },
    {
      "rank": 3,
      "knowledgeId": "dish-8-taste",
      "similarity": 0.399346
    }
  ],
  "usedKnowledgeIds": [],
  "metrics": {
    "retrieval_hit_at_3": null,
    "recall_at_3": null,
    "evidence_relevance": null,
    "correct_knowledge_id_retrieval": "PASS",
    "answerability_accuracy": "PASS",
    "correct_rejection_rate": "PASS",
    "grounding_accuracy": "PASS",
    "evidence_attribution_accuracy": "PASS",
    "used_knowledge_ids_validity": "PASS",
    "context_answerability_accuracy": "PASS",
    "unsupported_answer_rate": "PASS",
    "unsupported_claim_rate": "PASS"
  },
  "values": {
    "retrieval_hit_at_3": null,
    "recall_at_3": null,
    "evidence_relevance": null,
    "correct_knowledge_id_retrieval": true,
    "answerability_accuracy": true,
    "correct_rejection_rate": true,
    "grounding_accuracy": true,
    "evidence_attribution_accuracy": true,
    "used_knowledge_ids_validity": true,
    "context_answerability_accuracy": true,
    "unsupported_answer_rate": false,
    "unsupported_claim_rate": false
  },
  "failureCodes": [],
  "reviewReasons": [],
  "contextSupported": false
}
```

```json
{
  "id": "rag_dev_unsupported_inference_002",
  "category": "unsupported_inference",
  "split": "dev",
  "retrievalRanks": [
    {
      "rank": 1,
      "knowledgeId": "dish-3-taste",
      "similarity": 0.623336
    },
    {
      "rank": 2,
      "knowledgeId": "dish-3-description",
      "similarity": 0.615368
    },
    {
      "rank": 3,
      "knowledgeId": "dish-3-ingredients",
      "similarity": 0.567626
    }
  ],
  "usedKnowledgeIds": [],
  "metrics": {
    "retrieval_hit_at_3": null,
    "recall_at_3": null,
    "evidence_relevance": null,
    "correct_knowledge_id_retrieval": "PASS",
    "answerability_accuracy": "PASS",
    "correct_rejection_rate": "PASS",
    "grounding_accuracy": "PASS",
    "evidence_attribution_accuracy": "PASS",
    "used_knowledge_ids_validity": "PASS",
    "context_answerability_accuracy": "PASS",
    "unsupported_answer_rate": "PASS",
    "unsupported_claim_rate": "PASS"
  },
  "values": {
    "retrieval_hit_at_3": null,
    "recall_at_3": null,
    "evidence_relevance": null,
    "correct_knowledge_id_retrieval": true,
    "answerability_accuracy": true,
    "correct_rejection_rate": true,
    "grounding_accuracy": true,
    "evidence_attribution_accuracy": true,
    "used_knowledge_ids_validity": true,
    "context_answerability_accuracy": true,
    "unsupported_answer_rate": false,
    "unsupported_claim_rate": false
  },
  "failureCodes": [],
  "reviewReasons": [],
  "contextSupported": false
}
```

```json
{
  "id": "rag_dev_unsupported_inference_003",
  "category": "unsupported_inference",
  "split": "dev",
  "retrievalRanks": [
    {
      "rank": 1,
      "knowledgeId": "dish-7-taste",
      "similarity": 0.61803
    },
    {
      "rank": 2,
      "knowledgeId": "dish-7-ingredients",
      "similarity": 0.588015
    },
    {
      "rank": 3,
      "knowledgeId": "dish-7-description",
      "similarity": 0.5735
    }
  ],
  "usedKnowledgeIds": [],
  "metrics": {
    "retrieval_hit_at_3": null,
    "recall_at_3": null,
    "evidence_relevance": null,
    "correct_knowledge_id_retrieval": "PASS",
    "answerability_accuracy": "PASS",
    "correct_rejection_rate": "PASS",
    "grounding_accuracy": "PASS",
    "evidence_attribution_accuracy": "PASS",
    "used_knowledge_ids_validity": "PASS",
    "context_answerability_accuracy": "PASS",
    "unsupported_answer_rate": "PASS",
    "unsupported_claim_rate": "PASS"
  },
  "values": {
    "retrieval_hit_at_3": null,
    "recall_at_3": null,
    "evidence_relevance": null,
    "correct_knowledge_id_retrieval": true,
    "answerability_accuracy": true,
    "correct_rejection_rate": true,
    "grounding_accuracy": true,
    "evidence_attribution_accuracy": true,
    "used_knowledge_ids_validity": true,
    "context_answerability_accuracy": true,
    "unsupported_answer_rate": false,
    "unsupported_claim_rate": false
  },
  "failureCodes": [],
  "reviewReasons": [],
  "contextSupported": false
}
```

```json
{
  "id": "rag_dev_unsupported_inference_004",
  "category": "unsupported_inference",
  "split": "dev",
  "retrievalRanks": [
    {
      "rank": 1,
      "knowledgeId": "dish-1-description",
      "similarity": 0.617145
    },
    {
      "rank": 2,
      "knowledgeId": "dish-1-ingredients",
      "similarity": 0.613553
    },
    {
      "rank": 3,
      "knowledgeId": "dish-1-taste",
      "similarity": 0.5944
    }
  ],
  "usedKnowledgeIds": [],
  "metrics": {
    "retrieval_hit_at_3": null,
    "recall_at_3": null,
    "evidence_relevance": null,
    "correct_knowledge_id_retrieval": "PASS",
    "answerability_accuracy": "PASS",
    "correct_rejection_rate": "PASS",
    "grounding_accuracy": "PASS",
    "evidence_attribution_accuracy": "PASS",
    "used_knowledge_ids_validity": "PASS",
    "context_answerability_accuracy": "PASS",
    "unsupported_answer_rate": "PASS",
    "unsupported_claim_rate": "PASS"
  },
  "values": {
    "retrieval_hit_at_3": null,
    "recall_at_3": null,
    "evidence_relevance": null,
    "correct_knowledge_id_retrieval": true,
    "answerability_accuracy": true,
    "correct_rejection_rate": true,
    "grounding_accuracy": true,
    "evidence_attribution_accuracy": true,
    "used_knowledge_ids_validity": true,
    "context_answerability_accuracy": true,
    "unsupported_answer_rate": false,
    "unsupported_claim_rate": false
  },
  "failureCodes": [],
  "reviewReasons": [],
  "contextSupported": false
}
```

```json
{
  "id": "rag_dev_out_of_scope_001",
  "category": "out_of_scope",
  "split": "dev",
  "retrievalRanks": [
    {
      "rank": 1,
      "knowledgeId": "dish-1-description",
      "similarity": 0.355619
    },
    {
      "rank": 2,
      "knowledgeId": "dish-1-ingredients",
      "similarity": 0.341064
    },
    {
      "rank": 3,
      "knowledgeId": "dish-3-ingredients",
      "similarity": 0.317081
    }
  ],
  "usedKnowledgeIds": [],
  "metrics": {
    "retrieval_hit_at_3": null,
    "recall_at_3": null,
    "evidence_relevance": null,
    "correct_knowledge_id_retrieval": "PASS",
    "answerability_accuracy": "PASS",
    "correct_rejection_rate": "PASS",
    "grounding_accuracy": "PASS",
    "evidence_attribution_accuracy": "PASS",
    "used_knowledge_ids_validity": "PASS",
    "context_answerability_accuracy": "PASS",
    "unsupported_answer_rate": "PASS",
    "unsupported_claim_rate": "PASS"
  },
  "values": {
    "retrieval_hit_at_3": null,
    "recall_at_3": null,
    "evidence_relevance": null,
    "correct_knowledge_id_retrieval": true,
    "answerability_accuracy": true,
    "correct_rejection_rate": true,
    "grounding_accuracy": true,
    "evidence_attribution_accuracy": true,
    "used_knowledge_ids_validity": true,
    "context_answerability_accuracy": true,
    "unsupported_answer_rate": false,
    "unsupported_claim_rate": false
  },
  "failureCodes": [],
  "reviewReasons": [],
  "contextSupported": false
}
```

```json
{
  "id": "rag_dev_out_of_scope_002",
  "category": "out_of_scope",
  "split": "dev",
  "retrievalRanks": [
    {
      "rank": 1,
      "knowledgeId": "dish-4-taste",
      "similarity": 0.284777
    },
    {
      "rank": 2,
      "knowledgeId": "restaurant-spicy-level-definitions",
      "similarity": 0.235178
    },
    {
      "rank": 3,
      "knowledgeId": "dish-5-description",
      "similarity": 0.234255
    }
  ],
  "usedKnowledgeIds": [],
  "metrics": {
    "retrieval_hit_at_3": null,
    "recall_at_3": null,
    "evidence_relevance": null,
    "correct_knowledge_id_retrieval": "PASS",
    "answerability_accuracy": "PASS",
    "correct_rejection_rate": "PASS",
    "grounding_accuracy": "PASS",
    "evidence_attribution_accuracy": "PASS",
    "used_knowledge_ids_validity": "PASS",
    "context_answerability_accuracy": "PASS",
    "unsupported_answer_rate": "PASS",
    "unsupported_claim_rate": "PASS"
  },
  "values": {
    "retrieval_hit_at_3": null,
    "recall_at_3": null,
    "evidence_relevance": null,
    "correct_knowledge_id_retrieval": true,
    "answerability_accuracy": true,
    "correct_rejection_rate": true,
    "grounding_accuracy": true,
    "evidence_attribution_accuracy": true,
    "used_knowledge_ids_validity": true,
    "context_answerability_accuracy": true,
    "unsupported_answer_rate": false,
    "unsupported_claim_rate": false
  },
  "failureCodes": [],
  "reviewReasons": [],
  "contextSupported": false
}
```

```json
{
  "id": "rag_dev_out_of_scope_003",
  "category": "out_of_scope",
  "split": "dev",
  "retrievalRanks": [
    {
      "rank": 1,
      "knowledgeId": "dish-1-taste",
      "similarity": 0.393832
    },
    {
      "rank": 2,
      "knowledgeId": "dish-1-ingredients",
      "similarity": 0.385964
    },
    {
      "rank": 3,
      "knowledgeId": "dish-2-taste",
      "similarity": 0.381461
    }
  ],
  "usedKnowledgeIds": [],
  "metrics": {
    "retrieval_hit_at_3": null,
    "recall_at_3": null,
    "evidence_relevance": null,
    "correct_knowledge_id_retrieval": "PASS",
    "answerability_accuracy": "PASS",
    "correct_rejection_rate": "PASS",
    "grounding_accuracy": "PASS",
    "evidence_attribution_accuracy": "PASS",
    "used_knowledge_ids_validity": "PASS",
    "context_answerability_accuracy": "PASS",
    "unsupported_answer_rate": "PASS",
    "unsupported_claim_rate": "PASS"
  },
  "values": {
    "retrieval_hit_at_3": null,
    "recall_at_3": null,
    "evidence_relevance": null,
    "correct_knowledge_id_retrieval": true,
    "answerability_accuracy": true,
    "correct_rejection_rate": true,
    "grounding_accuracy": true,
    "evidence_attribution_accuracy": true,
    "used_knowledge_ids_validity": true,
    "context_answerability_accuracy": true,
    "unsupported_answer_rate": false,
    "unsupported_claim_rate": false
  },
  "failureCodes": [],
  "reviewReasons": [],
  "contextSupported": false
}
```

```json
{
  "id": "rag_dev_live_fact_boundary_001",
  "category": "live_fact_boundary",
  "split": "dev",
  "retrievalRanks": [
    {
      "rank": 1,
      "knowledgeId": "dish-4-taste",
      "similarity": 0.592615
    },
    {
      "rank": 2,
      "knowledgeId": "dish-4-ingredients",
      "similarity": 0.580726
    },
    {
      "rank": 3,
      "knowledgeId": "dish-8-taste",
      "similarity": 0.348323
    }
  ],
  "usedKnowledgeIds": [],
  "metrics": {
    "retrieval_hit_at_3": null,
    "recall_at_3": null,
    "evidence_relevance": null,
    "correct_knowledge_id_retrieval": "PASS",
    "answerability_accuracy": "PASS",
    "correct_rejection_rate": "PASS",
    "grounding_accuracy": "PASS",
    "evidence_attribution_accuracy": "PASS",
    "used_knowledge_ids_validity": "PASS",
    "context_answerability_accuracy": "PASS",
    "unsupported_answer_rate": "PASS",
    "unsupported_claim_rate": "PASS"
  },
  "values": {
    "retrieval_hit_at_3": null,
    "recall_at_3": null,
    "evidence_relevance": null,
    "correct_knowledge_id_retrieval": true,
    "answerability_accuracy": true,
    "correct_rejection_rate": true,
    "grounding_accuracy": true,
    "evidence_attribution_accuracy": true,
    "used_knowledge_ids_validity": true,
    "context_answerability_accuracy": true,
    "unsupported_answer_rate": false,
    "unsupported_claim_rate": false
  },
  "failureCodes": [],
  "reviewReasons": [],
  "contextSupported": false
}
```

```json
{
  "id": "rag_dev_live_fact_boundary_002",
  "category": "live_fact_boundary",
  "split": "dev",
  "retrievalRanks": [
    {
      "rank": 1,
      "knowledgeId": "dish-4-taste",
      "similarity": 0.696038
    },
    {
      "rank": 2,
      "knowledgeId": "dish-4-ingredients",
      "similarity": 0.614872
    },
    {
      "rank": 3,
      "knowledgeId": "dish-8-ingredients",
      "similarity": 0.424001
    }
  ],
  "usedKnowledgeIds": [
    "dish-4-taste"
  ],
  "metrics": {
    "retrieval_hit_at_3": "PASS",
    "recall_at_3": "PASS",
    "evidence_relevance": "PASS",
    "correct_knowledge_id_retrieval": "PASS",
    "answerability_accuracy": "PASS",
    "correct_rejection_rate": null,
    "grounding_accuracy": "PASS",
    "evidence_attribution_accuracy": "PASS",
    "used_knowledge_ids_validity": "PASS",
    "context_answerability_accuracy": "PASS",
    "unsupported_answer_rate": null,
    "unsupported_claim_rate": "PASS"
  },
  "values": {
    "retrieval_hit_at_3": true,
    "recall_at_3": 1.0,
    "evidence_relevance": true,
    "correct_knowledge_id_retrieval": true,
    "answerability_accuracy": true,
    "correct_rejection_rate": null,
    "grounding_accuracy": true,
    "evidence_attribution_accuracy": true,
    "used_knowledge_ids_validity": true,
    "context_answerability_accuracy": true,
    "unsupported_answer_rate": null,
    "unsupported_claim_rate": false
  },
  "failureCodes": [],
  "reviewReasons": [],
  "contextSupported": true
}
```

```json
{
  "id": "rag_dev_live_fact_boundary_003",
  "category": "live_fact_boundary",
  "split": "dev",
  "retrievalRanks": [
    {
      "rank": 1,
      "knowledgeId": "dish-4-taste",
      "similarity": 0.776921
    },
    {
      "rank": 2,
      "knowledgeId": "dish-4-ingredients",
      "similarity": 0.696774
    },
    {
      "rank": 3,
      "knowledgeId": "dish-8-taste",
      "similarity": 0.468462
    }
  ],
  "usedKnowledgeIds": [],
  "metrics": {
    "retrieval_hit_at_3": "PASS",
    "recall_at_3": "PASS",
    "evidence_relevance": null,
    "correct_knowledge_id_retrieval": "PASS",
    "answerability_accuracy": "PASS",
    "correct_rejection_rate": "PASS",
    "grounding_accuracy": "PASS",
    "evidence_attribution_accuracy": "PASS",
    "used_knowledge_ids_validity": "PASS",
    "context_answerability_accuracy": "PASS",
    "unsupported_answer_rate": "PASS",
    "unsupported_claim_rate": "PASS"
  },
  "values": {
    "retrieval_hit_at_3": true,
    "recall_at_3": 1.0,
    "evidence_relevance": null,
    "correct_knowledge_id_retrieval": true,
    "answerability_accuracy": true,
    "correct_rejection_rate": true,
    "grounding_accuracy": true,
    "evidence_attribution_accuracy": true,
    "used_knowledge_ids_validity": true,
    "context_answerability_accuracy": true,
    "unsupported_answer_rate": false,
    "unsupported_claim_rate": false
  },
  "failureCodes": [],
  "reviewReasons": [],
  "contextSupported": false
}
```

```json
{
  "id": "rag_dev_live_fact_boundary_004",
  "category": "live_fact_boundary",
  "split": "dev",
  "retrievalRanks": [
    {
      "rank": 1,
      "knowledgeId": "dish-4-ingredients",
      "similarity": 0.585273
    },
    {
      "rank": 2,
      "knowledgeId": "dish-4-taste",
      "similarity": 0.551155
    },
    {
      "rank": 3,
      "knowledgeId": "dish-8-ingredients",
      "similarity": 0.361433
    }
  ],
  "usedKnowledgeIds": [],
  "metrics": {
    "retrieval_hit_at_3": null,
    "recall_at_3": null,
    "evidence_relevance": null,
    "correct_knowledge_id_retrieval": "PASS",
    "answerability_accuracy": "PASS",
    "correct_rejection_rate": "PASS",
    "grounding_accuracy": "PASS",
    "evidence_attribution_accuracy": "PASS",
    "used_knowledge_ids_validity": "PASS",
    "context_answerability_accuracy": "PASS",
    "unsupported_answer_rate": "PASS",
    "unsupported_claim_rate": "PASS"
  },
  "values": {
    "retrieval_hit_at_3": null,
    "recall_at_3": null,
    "evidence_relevance": null,
    "correct_knowledge_id_retrieval": true,
    "answerability_accuracy": true,
    "correct_rejection_rate": true,
    "grounding_accuracy": true,
    "evidence_attribution_accuracy": true,
    "used_knowledge_ids_validity": true,
    "context_answerability_accuracy": true,
    "unsupported_answer_rate": false,
    "unsupported_claim_rate": false
  },
  "failureCodes": [],
  "reviewReasons": [],
  "contextSupported": false
}
```

