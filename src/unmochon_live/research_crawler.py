"""Keep original Stage 3 controls; visit curated instruction seeds first."""
def crawler_factory(registry, transport, output):
    from stage3.crawler import GovernmentCrawler

    class InstructionCrawler(GovernmentCrawler):
        def _enqueue(self, url, depth, label, plan, proof=None, *, priority=None):
            if depth == 0 and label == 'seed':
                priority = 1000 - list(plan.seed_urls).index(url)
            return super()._enqueue(url, depth, label, plan, proof, priority=priority)

    return InstructionCrawler(registry, transport, output)
