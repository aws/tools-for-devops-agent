# Bedrock quota codes for common models

Use with `servicequotas:GetServiceQuota --service-code bedrock --quota-code <code>`: one call returns the
applied value, instead of paging the full `ListServiceQuotas` list (1,123 quotas over 54 pages, about 11 s of
agent time per page, tested 2026-11-11). A code here is a shortcut, never a fact: read the value **and** the
quota name live every time. If `GetServiceQuota` returns `NoSuchResourceException`, or a `QuotaName` that
does not name the model and form, the code is wrong or has changed: drop it and ask the user for the code
(api-quirks §18 step 2b).

Built 2026-11-08 from `ListServiceQuotas` (service code `bedrock`) in us-east-1 and us-west-2. Every code
listed with ✓ has the same name in both Regions (110 of 133); codes marked `us-east-1 only` were not
found in us-west-2. `NoSuchResourceException` shows only that this code does not exist in your Region,
not that the quota is absent. Models and quotas change: for a model missing here, ask the user for the
code (api-quirks §18 step 2b). Checked live on 2026-11-23: all 133 codes exist in us-east-1, and every
returned name names its model, form and quota type with the Adjustable value shown. On 2026-11-12, 91 newer
model names (e.g. Claude Fable 5, GPT-6 Sol, Gemma 3) had no row.

Form: `on-demand` = direct model ID; `cross-region` = geographic profile (`us.`, `eu.`, `apac.`, …);
`global` = `global.` profile; `latency-optimized` = `performanceConfig.latency = optimized` (its own
quota, separate from on-demand and cross-region; api-quirks §23); `mantle` = bedrock-mantle endpoint (separate input and output TPM);
`per-day` = `Model invocation max tokens per day` (applies to the model; the name says if cross-Region
calls count double). Most models have no tokens-per-day quota, but this table is a snapshot, not
proof: if a model or form is not listed, it is "not in the code table". Only a full
`ListServiceQuotas` list shows a quota is absent (api-quirks §18). Never use another model's value.

**Two codes for one form:** Anthropic Claude Sonnet 4.5 has two codes each for cross-region RPM,
cross-region TPM, global RPM and global TPM, and their names were not recorded when this table was
built. Read both codes, use the one whose returned `QuotaName` matches the model and form (api-quirks
§18 step 4), and report the code and name you used.

| Model (quota name) | Form | Kind | Code | Adjustable | Both Regions |
|---|---|---|---|---|---|
| Amazon Nova 2 Lite | cross-region | RPM | `L-F06F1187` | no | ✓ |
| Amazon Nova 2 Lite | cross-region | TPM | `L-C6F5908D` | yes | ✓ |
| Amazon Nova 2 Lite | global | RPM | `L-D5F39C2F` | yes | ✓ |
| Amazon Nova 2 Lite | global | TPD | `L-AD940EDE` | no | ✓ |
| Amazon Nova 2 Lite | global | TPM | `L-71C69B70` | yes | ✓ |
| Amazon Nova 2 Lite | per-day | TPD | `L-210172B5` | no | ✓ |
| Amazon Nova Lite | cross-region | RPM | `L-89F8391A` | no | ✓ |
| Amazon Nova Lite | cross-region | TPM | `L-7C42E72A` | yes | ✓ |
| Amazon Nova Lite | on-demand | RPM | `L-E386A278` | no | us-east-1 only |
| Amazon Nova Lite | on-demand | TPM | `L-70423BF8` | no | us-east-1 only |
| Amazon Nova Lite | per-day | TPD | `L-45E0AD92` | no | ✓ |
| Amazon Nova Micro | cross-region | RPM | `L-3F110E0F` | no | ✓ |
| Amazon Nova Micro | cross-region | TPM | `L-DC7FF66C` | yes | ✓ |
| Amazon Nova Micro | on-demand | RPM | `L-E118F160` | no | us-east-1 only |
| Amazon Nova Micro | on-demand | TPM | `L-CFA4FA0D` | no | us-east-1 only |
| Amazon Nova Micro | per-day | TPD | `L-D2912E70` | no | ✓ |
| Amazon Nova Premier | cross-region | RPM | `L-9AD981E7` | no | ✓ |
| Amazon Nova Premier | cross-region | TPM | `L-AA7FE948` | yes | ✓ |
| Amazon Nova Premier | per-day | TPD | `L-B1D7F4B9` | no | ✓ |
| Amazon Nova Pro | cross-region | RPM | `L-ED46B8C5` | no | ✓ |
| Amazon Nova Pro | cross-region | TPM | `L-C0326783` | yes | ✓ |
| Amazon Nova Pro | on-demand | RPM | `L-F2717A44` | no | us-east-1 only |
| Amazon Nova Pro | on-demand | TPM | `L-CE33604C` | no | us-east-1 only |
| Amazon Nova Pro | per-day | TPD | `L-D690997B` | no | ✓ |
| Amazon Nova Pro V1 | latency-optimized | RPM | `L-98317D9C` | no | ✓ |
| Amazon Nova Pro V1 | latency-optimized | TPM | `L-BF13118E` | no | ✓ |
| Amazon Titan Text Embeddings V2 | on-demand | RPM | `L-26C560CE` | no | ✓ |
| Amazon Titan Text Embeddings V2 | on-demand | TPM | `L-DE641971` | no | ✓ |
| Anthropic Claude Haiku 4.5 | cross-region | RPM | `L-CCA5DF70` | yes | ✓ |
| Anthropic Claude Haiku 4.5 | cross-region | TPM | `L-58BE175A` | yes | ✓ |
| Anthropic Claude Haiku 4.5 | global | RPM | `L-E5084BBA` | yes | ✓ |
| Anthropic Claude Haiku 4.5 | global | TPM | `L-9A11C666` | yes | ✓ |
| Anthropic Claude Haiku 5.5 | cross-region | TPM | `L-47520EB7` | yes | ✓ |
| Anthropic Claude Haiku 5.5 | global | TPM | `L-F26CA8D1` | yes | ✓ |
| Anthropic Claude Opus 4.5 | cross-region | RPM | `L-27989F42` | yes | ✓ |
| Anthropic Claude Opus 4.5 | cross-region | TPM | `L-7007E9C9` | yes | ✓ |
| Anthropic Claude Opus 4.5 | global | RPM | `L-58424D95` | yes | ✓ |
| Anthropic Claude Opus 4.5 | global | TPD | `L-E2985A8E` | no | ✓ |
| Anthropic Claude Opus 4.5 | global | TPM | `L-3ABF6ACC` | yes | ✓ |
| Anthropic Claude Opus 4.5 | per-day | TPD | `L-F397ECBF` | no | ✓ |
| Anthropic Claude Opus 4.6 | cross-region | RPM | `L-11DFF789` | yes | ✓ |
| Anthropic Claude Opus 4.6 | cross-region | TPM | `L-0AD9BBE8` | yes | ✓ |
| Anthropic Claude Opus 4.6 | global | RPM | `L-3DD46812` | yes | ✓ |
| Anthropic Claude Opus 4.6 | global | TPM | `L-3DCCFAA4` | yes | ✓ |
| Anthropic Claude Opus 4.7 | cross-region | TPM | `L-5DB28B7B` | yes | ✓ |
| Anthropic Claude Opus 4.7 | global | TPM | `L-34152C1D` | yes | ✓ |
| Anthropic Claude Opus 4.8 | cross-region | TPM | `L-DB99DCDB` | yes | ✓ |
| Anthropic Claude Opus 4.8 | global | TPM | `L-4FCE27C7` | yes | ✓ |
| Anthropic Claude Opus 5 | cross-region | TPM | `L-99296DCD` | yes | ✓ |
| Anthropic Claude Opus 5 | global | TPM | `L-D73B1244` | yes | ✓ |
| Anthropic Claude Opus 5.5 | cross-region | TPM | `L-A4430697` | yes | ✓ |
| Anthropic Claude Opus 5.5 | global | TPM | `L-A103A344` | yes | ✓ |
| Anthropic Claude Sonnet 4.5 | cross-region | RPM | `L-A052927A` | yes | ✓ |
| Anthropic Claude Sonnet 4.5 | cross-region | RPM | `L-4A6BFAB1` | yes | ✓ |
| Anthropic Claude Sonnet 4.5 | cross-region | TPM | `L-8EA73537` | yes | ✓ |
| Anthropic Claude Sonnet 4.5 | cross-region | TPM | `L-F4DDD3EB` | yes | ✓ |
| Anthropic Claude Sonnet 4.5 | global | RPM | `L-C0D53EFB` | yes | ✓ |
| Anthropic Claude Sonnet 4.5 | global | RPM | `L-DB84CE56` | yes | ✓ |
| Anthropic Claude Sonnet 4.5 | global | TPD | `L-229A5DEC` | no | ✓ |
| Anthropic Claude Sonnet 4.5 | global | TPM | `L-4B26E44A` | yes | ✓ |
| Anthropic Claude Sonnet 4.5 | global | TPM | `L-27C57EE8` | yes | ✓ |
| Anthropic Claude Sonnet 4.5 | per-day | TPD | `L-E107194C` | no | ✓ |
| Anthropic Claude Sonnet 4.6 | cross-region | RPM | `L-00FF3314` | yes | ✓ |
| Anthropic Claude Sonnet 4.6 | cross-region | TPM | `L-15B8E632` | yes | ✓ |
| Anthropic Claude Sonnet 4.6 | global | RPM | `L-F6E116D7` | yes | ✓ |
| Anthropic Claude Sonnet 4.6 | global | TPM | `L-7BEE40FB` | yes | ✓ |
| Anthropic Claude Sonnet 5 | cross-region | TPM | `L-D4FBCF4E` | yes | ✓ |
| Anthropic Claude Sonnet 5 | global | TPM | `L-DD84E5CA` | yes | ✓ |
| Anthropic Claude Sonnet 5.5 | cross-region | TPM | `L-94A31E46` | yes | ✓ |
| Anthropic Claude Sonnet 5.5 | global | TPM | `L-31AB82D0` | yes | ✓ |
| Claude Opus 4.7 | mantle | TPM-input | `L-54814DC6` | yes | us-east-1 only |
| Claude Opus 4.7 | mantle | TPM-output | `L-15CD18AC` | yes | us-east-1 only |
| Claude Opus 4.8 | mantle | TPM-input | `L-8528F119` | yes | us-east-1 only |
| Claude Opus 4.8 | mantle | TPM-output | `L-37491D63` | yes | us-east-1 only |
| Claude Opus 5 | mantle | TPM-input | `L-DF09248F` | yes | us-east-1 only |
| Claude Opus 5 | mantle | TPM-output | `L-EDC225D2` | yes | us-east-1 only |
| Claude Opus 5.5 | mantle | TPM-input | `L-1BD3E8A2` | yes | us-east-1 only |
| Claude Opus 5.5 | mantle | TPM-output | `L-612AE448` | yes | us-east-1 only |
| Claude Sonnet 5 | mantle | TPM-input | `L-38EB0A61` | yes | us-east-1 only |
| Claude Sonnet 5 | mantle | TPM-output | `L-15830237` | yes | us-east-1 only |
| Cohere Embed English | on-demand | RPM | `L-FF8E7864` | no | ✓ |
| Cohere Embed English | on-demand | TPM | `L-A2BE277A` | no | ✓ |
| Cohere Embed Multilingual | on-demand | RPM | `L-9E5BD0C6` | no | ✓ |
| Cohere Embed Multilingual | on-demand | TPM | `L-C2F86908` | no | ✓ |
| Cohere Embed V4 | cross-region | RPM | `L-EB8C1F30` | no | ✓ |
| Cohere Embed V4 | cross-region | TPM | `L-4C3F0FE6` | yes | ✓ |
| Cohere Embed V4 | global | RPM | `L-7089DC7D` | yes | ✓ |
| Cohere Embed V4 | global | TPD | `L-795ADAB0` | no | ✓ |
| Cohere Embed V4 | global | TPM | `L-02DFBB76` | yes | ✓ |
| Cohere Embed V4 | on-demand | RPM | `L-BE5FD99B` | no | us-east-1 only |
| Cohere Embed V4 | on-demand | TPM | `L-C47B85D5` | no | us-east-1 only |
| Cohere Embed V4 | per-day | TPD | `L-F1BB08BB` | no | ✓ |
| DeepSeek R1 V1 | cross-region | RPM | `L-F52323AB` | no | ✓ |
| DeepSeek R1 V1 | cross-region | TPM | `L-06B03968` | yes | ✓ |
| DeepSeek V3.2 | on-demand | RPM | `L-3AE31EFC` | no | ✓ |
| DeepSeek V3.2 | on-demand | TPM | `L-C43703DE` | no | ✓ |
| GPT-5.6 Luna | cross-region | TPM | `L-E3C70889` | yes | ✓ |
| GPT-5.6 Luna | global | TPM | `L-D983F7C0` | yes | ✓ |
| GPT-5.6 Luna | mantle | TPM-input | `L-31615887` | yes | ✓ |
| GPT-5.6 Luna | mantle | TPM-output | `L-D44E1D4E` | yes | ✓ |
| GPT-5.6 Sol | cross-region | TPM | `L-D94ECE3B` | yes | ✓ |
| GPT-5.6 Sol | global | TPM | `L-4D7537CF` | yes | ✓ |
| GPT-5.6 Sol | mantle | TPM-input | `L-137DD3C2` | yes | us-east-1 only |
| GPT-5.6 Sol | mantle | TPM-output | `L-C2E494BA` | yes | us-east-1 only |
| GPT-5.6 Terra | cross-region | TPM | `L-99936FBF` | yes | ✓ |
| GPT-5.6 Terra | global | TPM | `L-8E752C84` | yes | ✓ |
| GPT-5.6 Terra | mantle | TPM-input | `L-87594EB7` | yes | ✓ |
| GPT-5.6 Terra | mantle | TPM-output | `L-574688BD` | yes | ✓ |
| Meta Llama 4 Maverick | cross-region | RPM | `L-4F18EF2F` | no | ✓ |
| Meta Llama 4 Maverick | cross-region | TPM | `L-DE3FBBF4` | yes | ✓ |
| Meta Llama 4 Scout | cross-region | RPM | `L-751B753A` | no | ✓ |
| Meta Llama 4 Scout | cross-region | TPM | `L-532E6630` | yes | ✓ |
| Mistral 7B Instruct | on-demand | RPM | `L-D9A35062` | no | ✓ |
| Mistral AI Mistral 7B Instruct | on-demand | TPM | `L-02D831F1` | no | ✓ |
| Mistral AI Mistral 7B Instruct | per-day | TPD | `L-12056022` | no | ✓ |
| Mistral AI Mistral Large | on-demand | TPM | `L-01447289` | no | ✓ |
| Mistral AI Mistral Large | per-day | TPD | `L-7A3C4C1E` | no | ✓ |
| Mistral AI Mistral Small | on-demand | RPM | `L-1CBB0490` | no | us-east-1 only |
| Mistral AI Mistral Small | on-demand | TPM | `L-82C15FA8` | no | us-east-1 only |
| Mistral AI Mistral Small | per-day | TPD | `L-163043A1` | no | us-east-1 only |
| Mistral AI Mixtral 8X7B Instruct | per-day | TPD | `L-68D6B437` | no | ✓ |
| Mistral AI Mixtral 8X7BB Instruct | on-demand | TPM | `L-490F4D1F` | no | ✓ |
| Mistral Devstral 2 123b | on-demand | RPM | `L-0197660A` | no | ✓ |
| Mistral Devstral 2 123b | on-demand | TPM | `L-904A6762` | no | ✓ |
| Mistral Large | on-demand | RPM | `L-3AF844DB` | no | ✓ |
| Mistral Large 3 | on-demand | RPM | `L-5B274E24` | no | ✓ |
| Mistral Large 3 | on-demand | TPM | `L-C709F563` | no | ✓ |
| Mistral Mixtral 8x7b Instruct | on-demand | RPM | `L-FD938632` | no | ✓ |
| Mistral Pixtral Large 25.02 V1 | cross-region | RPM | `L-674F42D5` | no | ✓ |
| Mistral Pixtral Large 25.02 V1 | cross-region | TPM | `L-4B9F76B0` | yes | ✓ |
| Mistral Pixtral Large 25.02 V1 | per-day | TPD | `L-58280E37` | no | ✓ |
| OpenAI GPT OSS 120B | on-demand | RPM | `L-25B50707` | no | ✓ |
| OpenAI GPT OSS 120B | on-demand | TPM | `L-9DC5F595` | no | ✓ |
| OpenAI GPT OSS 20B | on-demand | RPM | `L-AF7F0545` | no | ✓ |
| OpenAI GPT OSS 20B | on-demand | TPM | `L-036E14D8` | no | ✓ |
