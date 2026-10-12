# RAG v2 Repository Release Implementation Plan

1. Overlay the reviewed local source, configuration, tests, reports, and small
   evaluation artifacts onto the history-preserving release branch.
2. Exclude local environments, caches, package metadata, downloaded models,
   generated indexes, and secrets.
3. Add reproducible runtime, development, and optional embedding requirement
   files using versions verified in the working environment.
4. Add a simple offline RAG command-line demonstration.
5. Update the root README and add the team update guide and project roadmap.
6. Run formatting/diff checks, the complete test suite, BM25 reconstruction,
   BM25 test evaluation, and offline end-to-end evaluation.
7. Verify repository size and scan tracked content for common secret patterns.
8. Commit the reviewed release contents.
9. Create the private University of Sydney GitHub repository
   `CS46-Scientific-RAG-Assistant-v2` and push the preserved history and release
   branch as its default branch.
10. Deliver the repository URL, commit hash, verification results, and the full
    team update guide in chat.
