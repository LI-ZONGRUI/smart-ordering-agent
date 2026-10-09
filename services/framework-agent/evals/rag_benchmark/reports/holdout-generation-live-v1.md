# RAG Retrieval + Evidence-first Grounding Benchmark v1

```json
{
  "benchmarkVersion": 1,
  "validatorVersion": 1,
  "observabilityVersion": 2,
  "mode": "live-generation",
  "split": "holdout",
  "casesInScope": 10,
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
      "applicable": 8,
      "pass": 8,
      "machineDetectedFail": 0,
      "review": 0,
      "conservativeAutomaticPassRate": 1.0,
      "determinateCheckCoverage": 1.0,
      "value": 1.0,
      "valueMeaning": "conservative-score"
    },
    "recall_at_3": {
      "applicable": 8,
      "pass": 8,
      "machineDetectedFail": 0,
      "review": 0,
      "conservativeAutomaticPassRate": 1.0,
      "determinateCheckCoverage": 1.0,
      "value": 1.0,
      "valueMeaning": "conservative-score"
    },
    "evidence_relevance": {
      "applicable": 7,
      "pass": 6,
      "machineDetectedFail": 1,
      "review": 0,
      "conservativeAutomaticPassRate": 0.8571428571428571,
      "determinateCheckCoverage": 1.0,
      "value": 0.8571428571428571,
      "valueMeaning": "conservative-score"
    },
    "correct_knowledge_id_retrieval": {
      "applicable": 10,
      "pass": 10,
      "machineDetectedFail": 0,
      "review": 0,
      "conservativeAutomaticPassRate": 1.0,
      "determinateCheckCoverage": 1.0,
      "value": 1.0,
      "valueMeaning": "conservative-score"
    },
    "answerability_accuracy": {
      "applicable": 10,
      "pass": 10,
      "machineDetectedFail": 0,
      "review": 0,
      "conservativeAutomaticPassRate": 1.0,
      "determinateCheckCoverage": 1.0,
      "value": 1.0,
      "valueMeaning": "conservative-score"
    },
    "correct_rejection_rate": {
      "applicable": 3,
      "pass": 3,
      "machineDetectedFail": 0,
      "review": 0,
      "conservativeAutomaticPassRate": 1.0,
      "determinateCheckCoverage": 1.0,
      "value": 1.0,
      "valueMeaning": "conservative-score"
    },
    "grounding_accuracy": {
      "applicable": 10,
      "pass": 10,
      "machineDetectedFail": 0,
      "review": 0,
      "conservativeAutomaticPassRate": 1.0,
      "determinateCheckCoverage": 1.0,
      "value": 1.0,
      "valueMeaning": "conservative-score"
    },
    "evidence_attribution_accuracy": {
      "applicable": 10,
      "pass": 10,
      "machineDetectedFail": 0,
      "review": 0,
      "conservativeAutomaticPassRate": 1.0,
      "determinateCheckCoverage": 1.0,
      "value": 1.0,
      "valueMeaning": "conservative-score"
    },
    "used_knowledge_ids_validity": {
      "applicable": 10,
      "pass": 10,
      "machineDetectedFail": 0,
      "review": 0,
      "conservativeAutomaticPassRate": 1.0,
      "determinateCheckCoverage": 1.0,
      "value": 1.0,
      "valueMeaning": "conservative-score"
    },
    "context_answerability_accuracy": {
      "applicable": 10,
      "pass": 10,
      "machineDetectedFail": 0,
      "review": 0,
      "conservativeAutomaticPassRate": 1.0,
      "determinateCheckCoverage": 1.0,
      "value": 1.0,
      "valueMeaning": "conservative-score"
    },
    "unsupported_answer_rate": {
      "applicable": 3,
      "pass": 3,
      "machineDetectedFail": 0,
      "review": 0,
      "conservativeAutomaticPassRate": 1.0,
      "determinateCheckCoverage": 1.0,
      "value": 0.0,
      "valueMeaning": "observed-error-lower-bound"
    },
    "unsupported_claim_rate": {
      "applicable": 10,
      "pass": 10,
      "machineDetectedFail": 0,
      "review": 0,
      "conservativeAutomaticPassRate": 1.0,
      "determinateCheckCoverage": 1.0,
      "value": 0.0,
      "valueMeaning": "observed-error-lower-bound"
    }
  },
  "casesRequiringReview": 0,
  "failureDistribution": {
    "EVIDENCE_SELECTION_MISS": 1
  },
  "reviewDistribution": {}
}
```

## Safe case diagnostics

```json
{
  "id": "rag_holdout_direct_fact_001",
  "category": "direct_fact",
  "split": "holdout",
  "retrievalRanks": [
    {
      "rank": 1,
      "knowledgeId": "dish-1-taste",
      "similarity": 0.842052
    },
    {
      "rank": 2,
      "knowledgeId": "dish-1-description",
      "similarity": 0.775454
    },
    {
      "rank": 3,
      "knowledgeId": "dish-1-ingredients",
      "similarity": 0.736607
    }
  ],
  "usedKnowledgeIds": [
    "dish-1-taste",
    "dish-1-description",
    "dish-1-ingredients"
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
  "id": "rag_holdout_direct_fact_002",
  "category": "direct_fact",
  "split": "holdout",
  "retrievalRanks": [
    {
      "rank": 1,
      "knowledgeId": "dish-6-description",
      "similarity": 0.939437
    },
    {
      "rank": 2,
      "knowledgeId": "dish-6-ingredients",
      "similarity": 0.851053
    },
    {
      "rank": 3,
      "knowledgeId": "dish-2-description",
      "similarity": 0.475573
    }
  ],
  "usedKnowledgeIds": [
    "dish-6-description",
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
  "id": "rag_holdout_paraphrase_001",
  "category": "paraphrase",
  "split": "holdout",
  "retrievalRanks": [
    {
      "rank": 1,
      "knowledgeId": "dish-3-ingredients",
      "similarity": 0.788867
    },
    {
      "rank": 2,
      "knowledgeId": "dish-7-ingredients",
      "similarity": 0.711217
    },
    {
      "rank": 3,
      "knowledgeId": "dish-3-description",
      "similarity": 0.663095
    }
  ],
  "usedKnowledgeIds": [
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
  "id": "rag_holdout_paraphrase_002",
  "category": "paraphrase",
  "split": "holdout",
  "retrievalRanks": [
    {
      "rank": 1,
      "knowledgeId": "restaurant-spicy-level-definitions",
      "similarity": 0.80988
    },
    {
      "rank": 2,
      "knowledgeId": "dish-1-taste",
      "similarity": 0.471373
    },
    {
      "rank": 3,
      "knowledgeId": "dish-4-taste",
      "similarity": 0.416035
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
  "id": "rag_holdout_multi_evidence_001",
  "category": "multi_evidence",
  "split": "holdout",
  "retrievalRanks": [
    {
      "rank": 1,
      "knowledgeId": "dish-5-ingredients",
      "similarity": 0.900331
    },
    {
      "rank": 2,
      "knowledgeId": "dish-5-description",
      "similarity": 0.888731
    },
    {
      "rank": 3,
      "knowledgeId": "dish-1-taste",
      "similarity": 0.603562
    }
  ],
  "usedKnowledgeIds": [
    "dish-5-description",
    "dish-5-ingredients"
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
  "id": "rag_holdout_multi_evidence_002",
  "category": "multi_evidence",
  "split": "holdout",
  "retrievalRanks": [
    {
      "rank": 1,
      "knowledgeId": "dish-7-taste",
      "similarity": 0.736731
    },
    {
      "rank": 2,
      "knowledgeId": "dish-3-taste",
      "similarity": 0.692234
    },
    {
      "rank": 3,
      "knowledgeId": "dish-3-ingredients",
      "similarity": 0.646079
    }
  ],
  "usedKnowledgeIds": [
    "dish-3-taste",
    "dish-7-taste"
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
  "id": "rag_holdout_similar_dish_001",
  "category": "similar_dish",
  "split": "holdout",
  "retrievalRanks": [
    {
      "rank": 1,
      "knowledgeId": "dish-5-ingredients",
      "similarity": 0.767926
    },
    {
      "rank": 2,
      "knowledgeId": "dish-6-ingredients",
      "similarity": 0.712648
    },
    {
      "rank": 3,
      "knowledgeId": "dish-6-description",
      "similarity": 0.681707
    }
  ],
  "usedKnowledgeIds": [
    "dish-5-ingredients"
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
  "id": "rag_holdout_unsupported_inference_001",
  "category": "unsupported_inference",
  "split": "holdout",
  "retrievalRanks": [
    {
      "rank": 1,
      "knowledgeId": "dish-4-ingredients",
      "similarity": 0.612881
    },
    {
      "rank": 2,
      "knowledgeId": "dish-4-taste",
      "similarity": 0.572121
    },
    {
      "rank": 3,
      "knowledgeId": "dish-8-ingredients",
      "similarity": 0.402857
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
  "id": "rag_holdout_out_of_scope_001",
  "category": "out_of_scope",
  "split": "holdout",
  "retrievalRanks": [
    {
      "rank": 1,
      "knowledgeId": "dish-1-description",
      "similarity": 0.393309
    },
    {
      "rank": 2,
      "knowledgeId": "dish-3-description",
      "similarity": 0.374892
    },
    {
      "rank": 3,
      "knowledgeId": "dish-7-description",
      "similarity": 0.358011
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
  "id": "rag_holdout_live_fact_boundary_001",
  "category": "live_fact_boundary",
  "split": "holdout",
  "retrievalRanks": [
    {
      "rank": 1,
      "knowledgeId": "dish-8-taste",
      "similarity": 0.806567
    },
    {
      "rank": 2,
      "knowledgeId": "dish-8-ingredients",
      "similarity": 0.734048
    },
    {
      "rank": 3,
      "knowledgeId": "dish-2-taste",
      "similarity": 0.56123
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

