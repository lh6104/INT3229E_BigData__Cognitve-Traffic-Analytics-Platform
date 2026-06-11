# Final Report Checklist

Use this checklist before converting `docs/final_report_draft.md` into the final IEEE-style submission.

## Required Structure

- [x] Title is present.
- [x] Abstract is present and approximately 150-250 words.
- [x] Keywords are present.
- [x] Introduction is present.
- [x] Problem Statement and Objectives are present.
- [x] System Overview is present.
- [x] Data Sources and Processing Pipeline is present.
- [x] Geospatial Traffic Analytics is present.
- [x] Predictive Analytics Method is present.
- [x] Predicted Congestion Hotspots is present.
- [x] Prototype Implementation is present.
- [x] Results and Evaluation is present.
- [x] Limitations are present.
- [x] Future Work is present.
- [x] Conclusion is present.
- [x] References section is present.

## Expected Results Coverage

- [x] Integrate heterogeneous traffic data.
- [x] Process geospatial traffic data.
- [x] Analyze real-time or near-real-time traffic patterns.
- [x] Apply predictive analytics to traffic data.
- [x] Predict congestion hotspots.
- [x] Provide a decision-support dashboard.
- [x] Describe prototype demo.
- [x] Mention Docker/test reproducibility.

## Real vs Demo/Limited Claims

- [x] Real: FastAPI backend.
- [x] Real: raw to Silver to Gold local pipeline.
- [x] Real: TomTom traffic snapshots.
- [x] Real: Hanoi local Gold data with approximately 75 segments.
- [x] Real: geometry coverage for current Hanoi demo data.
- [x] Real: dashboard summary and trend endpoints.
- [x] Real: Live Map GeoJSON endpoint.
- [x] Real: alerts and current hotspots endpoints.
- [x] Real: LightGBM 15m and 60m forecast endpoints.
- [x] Real: predicted hotspot endpoint as a demo rule layer.
- [x] Limited: not full-city Hanoi coverage.
- [x] Limited: batch/snapshot ingestion, not production streaming.
- [x] Limited: partial feature fill in model inference.
- [x] Demo/static: Monitoring/System Health.
- [x] Demo/static: Explanations page, not real SHAP.
- [x] Limited: Neo4j exists in stack but is not used in main demo.
- [x] Limited: model artifacts should not be committed to normal Git history.

## Screenshots To Capture

- [ ] `/demo` full page or top half showing project summary and metrics.
- [ ] `/demo` Forecast section showing 15m and 60m predicted speed.
- [ ] `/demo` What is Real vs Demo section.
- [ ] Live Map showing Hanoi GeoJSON traffic segments.
- [ ] Forecast page showing selected real segment, model artifact/source, and feature coverage.
- [ ] Hotspots page showing current hotspot clusters.
- [ ] FastAPI Swagger page for `/hotspots/predicted`.
- [ ] Terminal or CI screenshot showing backend tests passed, if required by instructor.
- [ ] Terminal or CI screenshot showing frontend build passed, if required by instructor.

## Figures and Tables To Add

- [x] Mermaid architecture diagram draft is included.
- [ ] Replace Mermaid diagram with an IEEE-ready figure if the final template does not support Mermaid.
- [x] Data coverage table is included.
- [x] Model evaluation table is included.
- [ ] Add a screenshot figure for the `/demo` page.
- [ ] Add a screenshot figure for the Live Map.
- [ ] Add a screenshot figure for Forecast/Predicted Hotspots.
- [ ] Add a table mapping API endpoints to frontend sections if space allows.

## Citations To Verify

- [ ] TomTom Traffic API documentation URL and access date.
- [ ] LightGBM documentation or original LightGBM paper.
- [ ] FastAPI documentation URL and access date.
- [ ] React documentation URL and access date, if cited.
- [ ] Vite documentation URL and access date, if cited.
- [ ] IEEE conference template citation or formatting note.
- [ ] At least one intelligent transportation systems reference.
- [ ] At least one short-term traffic forecasting reference.
- [ ] At least one smart-city traffic analytics reference.

## Course/Team Information To Fill

- [ ] Student full names.
- [ ] Student IDs.
- [ ] Class or section.
- [ ] Course name.
- [ ] Instructor name.
- [ ] University or faculty name.
- [ ] Submission date.
- [ ] Team member contribution table, if required.
- [ ] GitHub repository link, if allowed.
- [ ] Demo video link, if required.

## Final Editing Notes

- [ ] Convert "approximately" values only if final audited numbers change.
- [ ] Do not claim production readiness.
- [ ] Do not claim full-city Hanoi coverage.
- [ ] Do not claim full real-time streaming until streaming is actually deployed.
- [ ] Do not claim SHAP/explainability is implemented unless real SHAP output is wired.
- [ ] Do not claim Neo4j routing/graph analytics is used in the demo.
- [ ] Keep model artifact paths out of screenshots if they reveal local machine details not needed for submission.
- [ ] Ensure `.env.local` and API keys are never included in the report, screenshots, or appendix.
- [ ] Check IEEE two-column formatting after moving the Markdown into the final template.
