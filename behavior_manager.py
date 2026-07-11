class BehaviorManager:
	def __init__(self):
		self.current = None

	def set(self, behavior, deck):

		if self.current:
			self.current.exit(deck)
		self.current = behavior
		self.current.enter(deck)

	def update(self, deck):
		if self.current:
			self.current.update(deck)
