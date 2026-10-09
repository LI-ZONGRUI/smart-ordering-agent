# RAG Retrieval + Evidence-first Grounding Benchmark v1

```json
{
  "benchmarkVersion": 1,
  "validatorVersion": 1,
  "observabilityVersion": 2,
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
      "pass": 21,
      "machineDetectedFail": 0,
      "review": 0,
      "conservativeAutomaticPassRate": 1.0,
      "determinateCheckCoverage": 1.0,
      "value": 1.0,
      "valueMeaning": "conservative-score"
    },
    "recall_at_3": {
      "applicable": 21,
      "pass": 20,
      "machineDetectedFail": 1,
      "review": 0,
      "conservativeAutomaticPassRate": 0.9523809523809523,
      "determinateCheckCoverage": 1.0,
      "value": 0.9761904761904762,
      "valueMeaning": "conservative-score"
    },
    "evidence_relevance": {
      "applicable": 20,
      "pass": 14,
      "machineDetectedFail": 6,
      "review": 0,
      "conservativeAutomaticPassRate": 0.7,
      "determinateCheckCoverage": 1.0,
      "value": 0.7,
      "valueMeaning": "conservative-score"
    },
    "correct_knowledge_id_retrieval": {
      "applicable": 30,
      "pass": 30,
      "machineDetectedFail": 0,
      "review": 0,
      "conservativeAutomaticPassRate": 1.0,
      "determinateCheckCoverage": 1.0,
      "value": 1.0,
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
      "pass": 9,
      "machineDetectedFail": 0,
      "review": 1,
      "conservativeAutomaticPassRate": 0.9,
      "determinateCheckCoverage": 0.9,
      "value": 0.9,
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
      "pass": 9,
      "machineDetectedFail": 0,
      "review": 1,
      "conservativeAutomaticPassRate": 0.9,
      "determinateCheckCoverage": 0.9,
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
    "EVIDENCE_SELECTION_MISS": 6
  },
  "reviewDistribution": {
    "GENERATION_NOT_OBSERVED": 1
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
      "similarity": 0.878129
    },
    {
      "rank": 2,
      "knowledgeId": "dish-1-description",
      "similarity": 0.831444
    },
    {
      "rank": 3,
      "knowledgeId": "dish-1-taste",
      "similarity": 0.772537
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
  "contextSupported": true,
  "diagnostics": {
    "failureStage": "NONE",
    "errorCategory": "NONE",
    "timeoutScope": "NONE",
    "failedOperation": "NONE",
    "retrievalCompleted": true,
    "generationState": "COMPLETED",
    "durationBucket": "1_TO_5S"
  },
  "evidenceSelection": {
    "requiredKnowledgeIds": [
      "dish-1-ingredients"
    ],
    "requiredEvidenceGroups": [
      [
        "dish-1-ingredients"
      ]
    ],
    "retrievedKnowledgeIds": [
      "dish-1-ingredients",
      "dish-1-description",
      "dish-1-taste"
    ],
    "usedKnowledgeIds": [
      "dish-1-ingredients"
    ],
    "missingRequiredEvidenceGroups": [],
    "missingRequiredKnowledgeIds": [],
    "missingSelectedEvidenceGroups": [],
    "extraSelectedKnowledgeIds": []
  }
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
      "similarity": 0.963111
    },
    {
      "rank": 2,
      "knowledgeId": "dish-2-taste",
      "similarity": 0.834377
    },
    {
      "rank": 3,
      "knowledgeId": "dish-2-ingredients",
      "similarity": 0.779965
    }
  ],
  "usedKnowledgeIds": [
    "dish-2-description",
    "dish-2-taste"
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
  "contextSupported": true,
  "diagnostics": {
    "failureStage": "NONE",
    "errorCategory": "NONE",
    "timeoutScope": "NONE",
    "failedOperation": "NONE",
    "retrievalCompleted": true,
    "generationState": "COMPLETED",
    "durationBucket": "1_TO_5S"
  },
  "evidenceSelection": {
    "requiredKnowledgeIds": [
      "dish-2-description",
      "dish-2-taste"
    ],
    "requiredEvidenceGroups": [
      [
        "dish-2-description",
        "dish-2-taste"
      ]
    ],
    "retrievedKnowledgeIds": [
      "dish-2-description",
      "dish-2-taste",
      "dish-2-ingredients"
    ],
    "usedKnowledgeIds": [
      "dish-2-description",
      "dish-2-taste"
    ],
    "missingRequiredEvidenceGroups": [],
    "missingRequiredKnowledgeIds": [],
    "missingSelectedEvidenceGroups": [],
    "extraSelectedKnowledgeIds": []
  }
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
      "similarity": 0.864446
    },
    {
      "rank": 2,
      "knowledgeId": "dish-3-ingredients",
      "similarity": 0.751371
    },
    {
      "rank": 3,
      "knowledgeId": "dish-3-taste",
      "similarity": 0.692232
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
  "contextSupported": true,
  "diagnostics": {
    "failureStage": "NONE",
    "errorCategory": "NONE",
    "timeoutScope": "NONE",
    "failedOperation": "NONE",
    "retrievalCompleted": true,
    "generationState": "COMPLETED",
    "durationBucket": "1_TO_5S"
  },
  "evidenceSelection": {
    "requiredKnowledgeIds": [
      "dish-3-description",
      "dish-3-ingredients"
    ],
    "requiredEvidenceGroups": [
      [
        "dish-3-description",
        "dish-3-ingredients"
      ]
    ],
    "retrievedKnowledgeIds": [
      "dish-3-description",
      "dish-3-ingredients",
      "dish-3-taste"
    ],
    "usedKnowledgeIds": [
      "dish-3-description",
      "dish-3-ingredients"
    ],
    "missingRequiredEvidenceGroups": [],
    "missingRequiredKnowledgeIds": [],
    "missingSelectedEvidenceGroups": [],
    "extraSelectedKnowledgeIds": []
  }
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
      "similarity": 0.904978
    },
    {
      "rank": 2,
      "knowledgeId": "dish-4-taste",
      "similarity": 0.672319
    },
    {
      "rank": 3,
      "knowledgeId": "dish-7-ingredients",
      "similarity": 0.593371
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
  "contextSupported": true,
  "diagnostics": {
    "failureStage": "NONE",
    "errorCategory": "NONE",
    "timeoutScope": "NONE",
    "failedOperation": "NONE",
    "retrievalCompleted": true,
    "generationState": "COMPLETED",
    "durationBucket": "1_TO_5S"
  },
  "evidenceSelection": {
    "requiredKnowledgeIds": [
      "dish-4-ingredients"
    ],
    "requiredEvidenceGroups": [
      [
        "dish-4-ingredients"
      ]
    ],
    "retrievedKnowledgeIds": [
      "dish-4-ingredients",
      "dish-4-taste",
      "dish-7-ingredients"
    ],
    "usedKnowledgeIds": [
      "dish-4-ingredients"
    ],
    "missingRequiredEvidenceGroups": [],
    "missingRequiredKnowledgeIds": [],
    "missingSelectedEvidenceGroups": [],
    "extraSelectedKnowledgeIds": []
  }
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
    "dish-7-description"
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
  "contextSupported": true,
  "diagnostics": {
    "failureStage": "NONE",
    "errorCategory": "NONE",
    "timeoutScope": "NONE",
    "failedOperation": "NONE",
    "retrievalCompleted": true,
    "generationState": "COMPLETED",
    "durationBucket": "1_TO_5S"
  },
  "evidenceSelection": {
    "requiredKnowledgeIds": [
      "dish-7-description"
    ],
    "requiredEvidenceGroups": [
      [
        "dish-7-description"
      ]
    ],
    "retrievedKnowledgeIds": [
      "dish-7-description",
      "dish-7-taste",
      "dish-7-ingredients"
    ],
    "usedKnowledgeIds": [
      "dish-7-description"
    ],
    "missingRequiredEvidenceGroups": [],
    "missingRequiredKnowledgeIds": [],
    "missingSelectedEvidenceGroups": [],
    "extraSelectedKnowledgeIds": []
  }
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
  "contextSupported": true,
  "diagnostics": {
    "failureStage": "NONE",
    "errorCategory": "NONE",
    "timeoutScope": "NONE",
    "failedOperation": "NONE",
    "retrievalCompleted": true,
    "generationState": "COMPLETED",
    "durationBucket": "1_TO_5S"
  },
  "evidenceSelection": {
    "requiredKnowledgeIds": [
      "restaurant-spicy-level-definitions"
    ],
    "requiredEvidenceGroups": [
      [
        "restaurant-spicy-level-definitions"
      ]
    ],
    "retrievedKnowledgeIds": [
      "restaurant-spicy-level-definitions",
      "dish-8-taste",
      "dish-2-taste"
    ],
    "usedKnowledgeIds": [
      "restaurant-spicy-level-definitions"
    ],
    "missingRequiredEvidenceGroups": [],
    "missingRequiredKnowledgeIds": [],
    "missingSelectedEvidenceGroups": [],
    "extraSelectedKnowledgeIds": []
  }
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
      "similarity": 0.837936
    },
    {
      "rank": 2,
      "knowledgeId": "dish-1-description",
      "similarity": 0.652384
    },
    {
      "rank": 3,
      "knowledgeId": "dish-5-description",
      "similarity": 0.610688
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
  "contextSupported": true,
  "diagnostics": {
    "failureStage": "NONE",
    "errorCategory": "NONE",
    "timeoutScope": "NONE",
    "failedOperation": "NONE",
    "retrievalCompleted": true,
    "generationState": "COMPLETED",
    "durationBucket": "1_TO_5S"
  },
  "evidenceSelection": {
    "requiredKnowledgeIds": [
      "dish-1-taste"
    ],
    "requiredEvidenceGroups": [
      [
        "dish-1-taste"
      ]
    ],
    "retrievedKnowledgeIds": [
      "dish-1-taste",
      "dish-1-description",
      "dish-5-description"
    ],
    "usedKnowledgeIds": [
      "dish-1-taste",
      "dish-1-description"
    ],
    "missingRequiredEvidenceGroups": [],
    "missingRequiredKnowledgeIds": [],
    "missingSelectedEvidenceGroups": [],
    "extraSelectedKnowledgeIds": [
      "dish-1-description"
    ]
  }
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
  "contextSupported": true,
  "diagnostics": {
    "failureStage": "NONE",
    "errorCategory": "NONE",
    "timeoutScope": "NONE",
    "failedOperation": "NONE",
    "retrievalCompleted": true,
    "generationState": "COMPLETED",
    "durationBucket": "1_TO_5S"
  },
  "evidenceSelection": {
    "requiredKnowledgeIds": [
      "dish-4-taste"
    ],
    "requiredEvidenceGroups": [
      [
        "dish-4-taste"
      ]
    ],
    "retrievedKnowledgeIds": [
      "dish-4-taste",
      "dish-4-ingredients",
      "dish-8-taste"
    ],
    "usedKnowledgeIds": [
      "dish-4-taste"
    ],
    "missingRequiredEvidenceGroups": [],
    "missingRequiredKnowledgeIds": [],
    "missingSelectedEvidenceGroups": [],
    "extraSelectedKnowledgeIds": []
  }
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
      "similarity": 0.803467
    },
    {
      "rank": 2,
      "knowledgeId": "dish-7-description",
      "similarity": 0.708869
    },
    {
      "rank": 3,
      "knowledgeId": "dish-7-ingredients",
      "similarity": 0.636582
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
  "contextSupported": true,
  "diagnostics": {
    "failureStage": "NONE",
    "errorCategory": "NONE",
    "timeoutScope": "NONE",
    "failedOperation": "NONE",
    "retrievalCompleted": true,
    "generationState": "COMPLETED",
    "durationBucket": "1_TO_5S"
  },
  "evidenceSelection": {
    "requiredKnowledgeIds": [
      "dish-7-taste"
    ],
    "requiredEvidenceGroups": [
      [
        "dish-7-taste"
      ]
    ],
    "retrievedKnowledgeIds": [
      "dish-7-taste",
      "dish-7-description",
      "dish-7-ingredients"
    ],
    "usedKnowledgeIds": [
      "dish-7-taste",
      "dish-7-description"
    ],
    "missingRequiredEvidenceGroups": [],
    "missingRequiredKnowledgeIds": [],
    "missingSelectedEvidenceGroups": [],
    "extraSelectedKnowledgeIds": [
      "dish-7-description"
    ]
  }
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
  "contextSupported": true,
  "diagnostics": {
    "failureStage": "NONE",
    "errorCategory": "NONE",
    "timeoutScope": "NONE",
    "failedOperation": "NONE",
    "retrievalCompleted": true,
    "generationState": "COMPLETED",
    "durationBucket": "1_TO_5S"
  },
  "evidenceSelection": {
    "requiredKnowledgeIds": [
      "dish-2-taste"
    ],
    "requiredEvidenceGroups": [
      [
        "dish-2-taste"
      ]
    ],
    "retrievedKnowledgeIds": [
      "dish-2-taste",
      "dish-2-description",
      "dish-8-taste"
    ],
    "usedKnowledgeIds": [
      "dish-2-taste",
      "dish-2-description"
    ],
    "missingRequiredEvidenceGroups": [],
    "missingRequiredKnowledgeIds": [],
    "missingSelectedEvidenceGroups": [],
    "extraSelectedKnowledgeIds": [
      "dish-2-description"
    ]
  }
}
```

```json
{
  "id": "rag_dev_paraphrase_005",
  "category": "paraphrase",
  "split": "dev",
  "retrievalRanks": [
    {
      "rank": 1,
      "knowledgeId": "dish-7-ingredients",
      "similarity": 0.78866
    },
    {
      "rank": 2,
      "knowledgeId": "dish-7-description",
      "similarity": 0.762047
    },
    {
      "rank": 3,
      "knowledgeId": "dish-3-ingredients",
      "similarity": 0.653018
    }
  ],
  "usedKnowledgeIds": [
    "dish-7-ingredients"
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
  "contextSupported": true,
  "diagnostics": {
    "failureStage": "NONE",
    "errorCategory": "NONE",
    "timeoutScope": "NONE",
    "failedOperation": "NONE",
    "retrievalCompleted": true,
    "generationState": "COMPLETED",
    "durationBucket": "1_TO_5S"
  },
  "evidenceSelection": {
    "requiredKnowledgeIds": [
      "dish-7-ingredients"
    ],
    "requiredEvidenceGroups": [
      [
        "dish-7-ingredients"
      ]
    ],
    "retrievedKnowledgeIds": [
      "dish-7-ingredients",
      "dish-7-description",
      "dish-3-ingredients"
    ],
    "usedKnowledgeIds": [
      "dish-7-ingredients"
    ],
    "missingRequiredEvidenceGroups": [],
    "missingRequiredKnowledgeIds": [],
    "missingSelectedEvidenceGroups": [],
    "extraSelectedKnowledgeIds": []
  }
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
      "similarity": 0.796518
    },
    {
      "rank": 2,
      "knowledgeId": "dish-1-description",
      "similarity": 0.756032
    },
    {
      "rank": 3,
      "knowledgeId": "dish-5-ingredients",
      "similarity": 0.748171
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
  "contextSupported": false,
  "diagnostics": {
    "failureStage": "NONE",
    "errorCategory": "NONE",
    "timeoutScope": "NONE",
    "failedOperation": "NONE",
    "retrievalCompleted": true,
    "generationState": "COMPLETED",
    "durationBucket": "1_TO_5S"
  },
  "evidenceSelection": {
    "requiredKnowledgeIds": [
      "dish-1-taste",
      "dish-1-ingredients"
    ],
    "requiredEvidenceGroups": [
      [
        "dish-1-taste"
      ],
      [
        "dish-1-ingredients"
      ]
    ],
    "retrievedKnowledgeIds": [
      "dish-1-ingredients",
      "dish-1-description",
      "dish-5-ingredients"
    ],
    "usedKnowledgeIds": [
      "dish-1-description",
      "dish-1-ingredients"
    ],
    "missingRequiredEvidenceGroups": [
      [
        "dish-1-taste"
      ]
    ],
    "missingRequiredKnowledgeIds": [
      "dish-1-taste"
    ],
    "missingSelectedEvidenceGroups": [
      [
        "dish-1-taste"
      ]
    ],
    "extraSelectedKnowledgeIds": [
      "dish-1-description"
    ]
  }
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
      "similarity": 0.803505
    },
    {
      "rank": 2,
      "knowledgeId": "dish-3-ingredients",
      "similarity": 0.737941
    },
    {
      "rank": 3,
      "knowledgeId": "dish-3-taste",
      "similarity": 0.717392
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
  "contextSupported": true,
  "diagnostics": {
    "failureStage": "NONE",
    "errorCategory": "NONE",
    "timeoutScope": "NONE",
    "failedOperation": "NONE",
    "retrievalCompleted": true,
    "generationState": "COMPLETED",
    "durationBucket": "1_TO_5S"
  },
  "evidenceSelection": {
    "requiredKnowledgeIds": [
      "dish-3-taste",
      "dish-3-description",
      "dish-3-ingredients"
    ],
    "requiredEvidenceGroups": [
      [
        "dish-3-taste"
      ],
      [
        "dish-3-description",
        "dish-3-ingredients"
      ]
    ],
    "retrievedKnowledgeIds": [
      "dish-3-description",
      "dish-3-ingredients",
      "dish-3-taste"
    ],
    "usedKnowledgeIds": [
      "dish-3-taste",
      "dish-3-description"
    ],
    "missingRequiredEvidenceGroups": [],
    "missingRequiredKnowledgeIds": [],
    "missingSelectedEvidenceGroups": [],
    "extraSelectedKnowledgeIds": []
  }
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
      "similarity": 0.778364
    },
    {
      "rank": 2,
      "knowledgeId": "dish-6-ingredients",
      "similarity": 0.766407
    },
    {
      "rank": 3,
      "knowledgeId": "dish-6-description",
      "similarity": 0.75823
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
  "contextSupported": true,
  "diagnostics": {
    "failureStage": "NONE",
    "errorCategory": "NONE",
    "timeoutScope": "NONE",
    "failedOperation": "NONE",
    "retrievalCompleted": true,
    "generationState": "COMPLETED",
    "durationBucket": "1_TO_5S"
  },
  "evidenceSelection": {
    "requiredKnowledgeIds": [
      "dish-2-ingredients",
      "dish-6-ingredients"
    ],
    "requiredEvidenceGroups": [
      [
        "dish-2-ingredients"
      ],
      [
        "dish-6-ingredients"
      ]
    ],
    "retrievedKnowledgeIds": [
      "dish-2-ingredients",
      "dish-6-ingredients",
      "dish-6-description"
    ],
    "usedKnowledgeIds": [
      "dish-2-ingredients",
      "dish-6-ingredients"
    ],
    "missingRequiredEvidenceGroups": [],
    "missingRequiredKnowledgeIds": [],
    "missingSelectedEvidenceGroups": [],
    "extraSelectedKnowledgeIds": []
  }
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
  "contextSupported": true,
  "diagnostics": {
    "failureStage": "NONE",
    "errorCategory": "NONE",
    "timeoutScope": "NONE",
    "failedOperation": "NONE",
    "retrievalCompleted": true,
    "generationState": "COMPLETED",
    "durationBucket": "1_TO_5S"
  },
  "evidenceSelection": {
    "requiredKnowledgeIds": [
      "dish-4-taste",
      "dish-4-ingredients"
    ],
    "requiredEvidenceGroups": [
      [
        "dish-4-taste"
      ],
      [
        "dish-4-ingredients"
      ]
    ],
    "retrievedKnowledgeIds": [
      "dish-4-taste",
      "dish-4-ingredients",
      "dish-7-ingredients"
    ],
    "usedKnowledgeIds": [
      "dish-4-taste",
      "dish-4-ingredients"
    ],
    "missingRequiredEvidenceGroups": [],
    "missingRequiredKnowledgeIds": [],
    "missingSelectedEvidenceGroups": [],
    "extraSelectedKnowledgeIds": []
  }
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
  "contextSupported": true,
  "diagnostics": {
    "failureStage": "NONE",
    "errorCategory": "NONE",
    "timeoutScope": "NONE",
    "failedOperation": "NONE",
    "retrievalCompleted": true,
    "generationState": "COMPLETED",
    "durationBucket": "1_TO_5S"
  },
  "evidenceSelection": {
    "requiredKnowledgeIds": [
      "dish-2-description"
    ],
    "requiredEvidenceGroups": [
      [
        "dish-2-description"
      ]
    ],
    "retrievedKnowledgeIds": [
      "dish-2-description",
      "dish-2-ingredients",
      "dish-2-taste"
    ],
    "usedKnowledgeIds": [
      "dish-2-description",
      "dish-2-ingredients",
      "dish-2-taste"
    ],
    "missingRequiredEvidenceGroups": [],
    "missingRequiredKnowledgeIds": [],
    "missingSelectedEvidenceGroups": [],
    "extraSelectedKnowledgeIds": [
      "dish-2-ingredients",
      "dish-2-taste"
    ]
  }
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
  "contextSupported": true,
  "diagnostics": {
    "failureStage": "NONE",
    "errorCategory": "NONE",
    "timeoutScope": "NONE",
    "failedOperation": "NONE",
    "retrievalCompleted": true,
    "generationState": "COMPLETED",
    "durationBucket": "1_TO_5S"
  },
  "evidenceSelection": {
    "requiredKnowledgeIds": [
      "dish-7-taste",
      "dish-4-taste"
    ],
    "requiredEvidenceGroups": [
      [
        "dish-7-taste"
      ],
      [
        "dish-4-taste"
      ]
    ],
    "retrievedKnowledgeIds": [
      "dish-7-taste",
      "dish-4-taste",
      "dish-7-description"
    ],
    "usedKnowledgeIds": [
      "dish-7-taste",
      "dish-4-taste"
    ],
    "missingRequiredEvidenceGroups": [],
    "missingRequiredKnowledgeIds": [],
    "missingSelectedEvidenceGroups": [],
    "extraSelectedKnowledgeIds": []
  }
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
  "contextSupported": true,
  "diagnostics": {
    "failureStage": "NONE",
    "errorCategory": "NONE",
    "timeoutScope": "NONE",
    "failedOperation": "NONE",
    "retrievalCompleted": true,
    "generationState": "COMPLETED",
    "durationBucket": "1_TO_5S"
  },
  "evidenceSelection": {
    "requiredKnowledgeIds": [
      "dish-1-description"
    ],
    "requiredEvidenceGroups": [
      [
        "dish-1-description"
      ]
    ],
    "retrievedKnowledgeIds": [
      "dish-5-description",
      "dish-1-description",
      "dish-5-ingredients"
    ],
    "usedKnowledgeIds": [
      "dish-1-description",
      "dish-5-description"
    ],
    "missingRequiredEvidenceGroups": [],
    "missingRequiredKnowledgeIds": [],
    "missingSelectedEvidenceGroups": [],
    "extraSelectedKnowledgeIds": [
      "dish-5-description"
    ]
  }
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
      "similarity": 0.813217
    },
    {
      "rank": 2,
      "knowledgeId": "dish-2-taste",
      "similarity": 0.77631
    },
    {
      "rank": 3,
      "knowledgeId": "dish-2-ingredients",
      "similarity": 0.743062
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
  "contextSupported": true,
  "diagnostics": {
    "failureStage": "NONE",
    "errorCategory": "NONE",
    "timeoutScope": "NONE",
    "failedOperation": "NONE",
    "retrievalCompleted": true,
    "generationState": "COMPLETED",
    "durationBucket": "1_TO_5S"
  },
  "evidenceSelection": {
    "requiredKnowledgeIds": [
      "dish-2-description",
      "dish-2-taste"
    ],
    "requiredEvidenceGroups": [
      [
        "dish-2-description",
        "dish-2-taste"
      ]
    ],
    "retrievedKnowledgeIds": [
      "dish-2-description",
      "dish-2-taste",
      "dish-2-ingredients"
    ],
    "usedKnowledgeIds": [
      "dish-2-description"
    ],
    "missingRequiredEvidenceGroups": [],
    "missingRequiredKnowledgeIds": [],
    "missingSelectedEvidenceGroups": [],
    "extraSelectedKnowledgeIds": []
  }
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
  "contextSupported": false,
  "diagnostics": {
    "failureStage": "NONE",
    "errorCategory": "NONE",
    "timeoutScope": "NONE",
    "failedOperation": "NONE",
    "retrievalCompleted": true,
    "generationState": "COMPLETED",
    "durationBucket": "1_TO_5S"
  },
  "evidenceSelection": {
    "requiredKnowledgeIds": [],
    "requiredEvidenceGroups": [],
    "retrievedKnowledgeIds": [
      "dish-4-ingredients",
      "dish-4-taste",
      "dish-8-taste"
    ],
    "usedKnowledgeIds": [],
    "missingRequiredEvidenceGroups": [],
    "missingRequiredKnowledgeIds": [],
    "missingSelectedEvidenceGroups": [],
    "extraSelectedKnowledgeIds": []
  }
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
      "similarity": 0.621345
    },
    {
      "rank": 2,
      "knowledgeId": "dish-3-description",
      "similarity": 0.616989
    },
    {
      "rank": 3,
      "knowledgeId": "dish-3-ingredients",
      "similarity": 0.566922
    }
  ],
  "usedKnowledgeIds": [],
  "metrics": {
    "retrieval_hit_at_3": null,
    "recall_at_3": null,
    "evidence_relevance": null,
    "correct_knowledge_id_retrieval": "PASS",
    "answerability_accuracy": "REVIEW",
    "correct_rejection_rate": "REVIEW",
    "grounding_accuracy": "REVIEW",
    "evidence_attribution_accuracy": "REVIEW",
    "used_knowledge_ids_validity": "REVIEW",
    "context_answerability_accuracy": "REVIEW",
    "unsupported_answer_rate": "REVIEW",
    "unsupported_claim_rate": "REVIEW"
  },
  "values": {
    "retrieval_hit_at_3": null,
    "recall_at_3": null,
    "evidence_relevance": null,
    "correct_knowledge_id_retrieval": true,
    "answerability_accuracy": false,
    "correct_rejection_rate": false,
    "grounding_accuracy": false,
    "evidence_attribution_accuracy": false,
    "used_knowledge_ids_validity": false,
    "context_answerability_accuracy": false,
    "unsupported_answer_rate": null,
    "unsupported_claim_rate": null
  },
  "failureCodes": [],
  "reviewReasons": [
    "GENERATION_NOT_OBSERVED"
  ],
  "contextSupported": false,
  "diagnostics": {
    "failureStage": "GENERATION_VALIDATION",
    "errorCategory": "RESPONSE_INVALID",
    "timeoutScope": "NONE",
    "failedOperation": "NONE",
    "retrievalCompleted": true,
    "generationState": "NOT_OBSERVED",
    "durationBucket": "1_TO_5S"
  },
  "evidenceSelection": {
    "requiredKnowledgeIds": [],
    "requiredEvidenceGroups": [],
    "retrievedKnowledgeIds": [
      "dish-3-taste",
      "dish-3-description",
      "dish-3-ingredients"
    ],
    "usedKnowledgeIds": [],
    "missingRequiredEvidenceGroups": [],
    "missingRequiredKnowledgeIds": [],
    "missingSelectedEvidenceGroups": null,
    "extraSelectedKnowledgeIds": null
  }
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
  "contextSupported": false,
  "diagnostics": {
    "failureStage": "NONE",
    "errorCategory": "NONE",
    "timeoutScope": "NONE",
    "failedOperation": "NONE",
    "retrievalCompleted": true,
    "generationState": "COMPLETED",
    "durationBucket": "1_TO_5S"
  },
  "evidenceSelection": {
    "requiredKnowledgeIds": [],
    "requiredEvidenceGroups": [],
    "retrievedKnowledgeIds": [
      "dish-7-taste",
      "dish-7-ingredients",
      "dish-7-description"
    ],
    "usedKnowledgeIds": [],
    "missingRequiredEvidenceGroups": [],
    "missingRequiredKnowledgeIds": [],
    "missingSelectedEvidenceGroups": [],
    "extraSelectedKnowledgeIds": []
  }
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
  "contextSupported": false,
  "diagnostics": {
    "failureStage": "NONE",
    "errorCategory": "NONE",
    "timeoutScope": "NONE",
    "failedOperation": "NONE",
    "retrievalCompleted": true,
    "generationState": "COMPLETED",
    "durationBucket": "1_TO_5S"
  },
  "evidenceSelection": {
    "requiredKnowledgeIds": [],
    "requiredEvidenceGroups": [],
    "retrievedKnowledgeIds": [
      "dish-1-description",
      "dish-1-ingredients",
      "dish-1-taste"
    ],
    "usedKnowledgeIds": [],
    "missingRequiredEvidenceGroups": [],
    "missingRequiredKnowledgeIds": [],
    "missingSelectedEvidenceGroups": [],
    "extraSelectedKnowledgeIds": []
  }
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
      "similarity": 0.352081
    },
    {
      "rank": 2,
      "knowledgeId": "dish-1-ingredients",
      "similarity": 0.335502
    },
    {
      "rank": 3,
      "knowledgeId": "dish-3-ingredients",
      "similarity": 0.313656
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
  "contextSupported": false,
  "diagnostics": {
    "failureStage": "NONE",
    "errorCategory": "NONE",
    "timeoutScope": "NONE",
    "failedOperation": "NONE",
    "retrievalCompleted": true,
    "generationState": "COMPLETED",
    "durationBucket": "5_TO_15S"
  },
  "evidenceSelection": {
    "requiredKnowledgeIds": [],
    "requiredEvidenceGroups": [],
    "retrievedKnowledgeIds": [
      "dish-1-description",
      "dish-1-ingredients",
      "dish-3-ingredients"
    ],
    "usedKnowledgeIds": [],
    "missingRequiredEvidenceGroups": [],
    "missingRequiredKnowledgeIds": [],
    "missingSelectedEvidenceGroups": [],
    "extraSelectedKnowledgeIds": []
  }
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
      "similarity": 0.286403
    },
    {
      "rank": 2,
      "knowledgeId": "dish-1-ingredients",
      "similarity": 0.236054
    },
    {
      "rank": 3,
      "knowledgeId": "restaurant-spicy-level-definitions",
      "similarity": 0.235353
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
  "contextSupported": false,
  "diagnostics": {
    "failureStage": "NONE",
    "errorCategory": "NONE",
    "timeoutScope": "NONE",
    "failedOperation": "NONE",
    "retrievalCompleted": true,
    "generationState": "COMPLETED",
    "durationBucket": "1_TO_5S"
  },
  "evidenceSelection": {
    "requiredKnowledgeIds": [],
    "requiredEvidenceGroups": [],
    "retrievedKnowledgeIds": [
      "dish-4-taste",
      "dish-1-ingredients",
      "restaurant-spicy-level-definitions"
    ],
    "usedKnowledgeIds": [],
    "missingRequiredEvidenceGroups": [],
    "missingRequiredKnowledgeIds": [],
    "missingSelectedEvidenceGroups": [],
    "extraSelectedKnowledgeIds": []
  }
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
      "similarity": 0.392895
    },
    {
      "rank": 2,
      "knowledgeId": "dish-1-ingredients",
      "similarity": 0.38693
    },
    {
      "rank": 3,
      "knowledgeId": "dish-2-taste",
      "similarity": 0.382053
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
  "contextSupported": false,
  "diagnostics": {
    "failureStage": "NONE",
    "errorCategory": "NONE",
    "timeoutScope": "NONE",
    "failedOperation": "NONE",
    "retrievalCompleted": true,
    "generationState": "COMPLETED",
    "durationBucket": "1_TO_5S"
  },
  "evidenceSelection": {
    "requiredKnowledgeIds": [],
    "requiredEvidenceGroups": [],
    "retrievedKnowledgeIds": [
      "dish-1-taste",
      "dish-1-ingredients",
      "dish-2-taste"
    ],
    "usedKnowledgeIds": [],
    "missingRequiredEvidenceGroups": [],
    "missingRequiredKnowledgeIds": [],
    "missingSelectedEvidenceGroups": [],
    "extraSelectedKnowledgeIds": []
  }
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
      "similarity": 0.595013
    },
    {
      "rank": 2,
      "knowledgeId": "dish-4-ingredients",
      "similarity": 0.584493
    },
    {
      "rank": 3,
      "knowledgeId": "dish-8-taste",
      "similarity": 0.351543
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
  "contextSupported": false,
  "diagnostics": {
    "failureStage": "NONE",
    "errorCategory": "NONE",
    "timeoutScope": "NONE",
    "failedOperation": "NONE",
    "retrievalCompleted": true,
    "generationState": "COMPLETED",
    "durationBucket": "1_TO_5S"
  },
  "evidenceSelection": {
    "requiredKnowledgeIds": [],
    "requiredEvidenceGroups": [],
    "retrievedKnowledgeIds": [
      "dish-4-taste",
      "dish-4-ingredients",
      "dish-8-taste"
    ],
    "usedKnowledgeIds": [],
    "missingRequiredEvidenceGroups": [],
    "missingRequiredKnowledgeIds": [],
    "missingSelectedEvidenceGroups": [],
    "extraSelectedKnowledgeIds": []
  }
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
  "contextSupported": true,
  "diagnostics": {
    "failureStage": "NONE",
    "errorCategory": "NONE",
    "timeoutScope": "NONE",
    "failedOperation": "NONE",
    "retrievalCompleted": true,
    "generationState": "COMPLETED",
    "durationBucket": "1_TO_5S"
  },
  "evidenceSelection": {
    "requiredKnowledgeIds": [
      "dish-4-taste"
    ],
    "requiredEvidenceGroups": [
      [
        "dish-4-taste"
      ]
    ],
    "retrievedKnowledgeIds": [
      "dish-4-taste",
      "dish-4-ingredients",
      "dish-8-ingredients"
    ],
    "usedKnowledgeIds": [
      "dish-4-taste"
    ],
    "missingRequiredEvidenceGroups": [],
    "missingRequiredKnowledgeIds": [],
    "missingSelectedEvidenceGroups": [],
    "extraSelectedKnowledgeIds": []
  }
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
      "similarity": 0.77812
    },
    {
      "rank": 2,
      "knowledgeId": "dish-4-ingredients",
      "similarity": 0.69816
    },
    {
      "rank": 3,
      "knowledgeId": "dish-8-taste",
      "similarity": 0.471562
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
  "contextSupported": false,
  "diagnostics": {
    "failureStage": "NONE",
    "errorCategory": "NONE",
    "timeoutScope": "NONE",
    "failedOperation": "NONE",
    "retrievalCompleted": true,
    "generationState": "COMPLETED",
    "durationBucket": "1_TO_5S"
  },
  "evidenceSelection": {
    "requiredKnowledgeIds": [
      "dish-4-taste"
    ],
    "requiredEvidenceGroups": [
      [
        "dish-4-taste"
      ]
    ],
    "retrievedKnowledgeIds": [
      "dish-4-taste",
      "dish-4-ingredients",
      "dish-8-taste"
    ],
    "usedKnowledgeIds": [],
    "missingRequiredEvidenceGroups": [],
    "missingRequiredKnowledgeIds": [],
    "missingSelectedEvidenceGroups": [
      [
        "dish-4-taste"
      ]
    ],
    "extraSelectedKnowledgeIds": []
  }
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
  "contextSupported": false,
  "diagnostics": {
    "failureStage": "NONE",
    "errorCategory": "NONE",
    "timeoutScope": "NONE",
    "failedOperation": "NONE",
    "retrievalCompleted": true,
    "generationState": "COMPLETED",
    "durationBucket": "1_TO_5S"
  },
  "evidenceSelection": {
    "requiredKnowledgeIds": [],
    "requiredEvidenceGroups": [],
    "retrievedKnowledgeIds": [
      "dish-4-ingredients",
      "dish-4-taste",
      "dish-8-ingredients"
    ],
    "usedKnowledgeIds": [],
    "missingRequiredEvidenceGroups": [],
    "missingRequiredKnowledgeIds": [],
    "missingSelectedEvidenceGroups": [],
    "extraSelectedKnowledgeIds": []
  }
}
```

