#!/usr/bin/env python

# game of snake using Tkinter, tested on winpython 2.7
# see global vars for options


from Tkinter import *
from collections import deque
from itertools import islice
from random import choice as random_choice

class Vector(tuple):
	# inherits from tuple, so it's unmutable
	@property
	def x(self):
		return self[0]

	@property
	def y(self):
		return self[1]

	def __add__(self, v): return Vector((self.x+v.x, self.y+v.y))
	def __sub__(self, v): return Vector((self.x-v.x, self.y-v.y))
	def __mul__(self, n): return Vector((self.x*n  , self.y*n  ))  # mult by *scalar*
	def __div__(self, n): return Vector((self.x//n , self.y//n ))  # floor div by *scalar*.
	def __neg__(self)   : return Vector((-self.x   , -self.y   ))
	def wrap(self, v)   : return Vector((self.x % v.x, self.y % v.y))  # 0-indexed: wrap(15,14) = 1, wrap(14,14) = 0


def P(x,y):
	# helper func so I don't have to write Vector((x,y)), but only P(x,y)
	return Vector((x,y))


# naming conventions:
# a p (for position) is a vector
# ps is a list of p
# wh is vector(width, weight)
# tl for topleft is a vector(x0,y0)
# size is a scalar

UP    = P(0,-1)
DOWN  = P(0,1)
LEFT  = P(-1,0)
RIGHT = P(1,0)

FIELD_WH = P(25,20)
SNAKE_INIT_SIZE = 3

NUMBER_OF_FOODS = 10
FOOD_INCREASE = 3  # how many segments does a snake grow after eating food
PERIOD = 200  # time between game ticks

SNAKE0_COLOR = 'green'
SNAKE1_COLOR = 'yellow'
FOOD_COLOR = 'red'
BG_COLOR = 'black'
COLLISION_COLOR = 'blue'

BLOCK_SIZE_C = 20
BLOCK_SIZE_DR = 5


class Visual_Block:
	"""
	A block is a 'cluster' of 3 rectangles (stored in a dict) that can be painted individually:
	 _____ _
	|     | |
	|  c  |r|
	|_____|_|
	|__d__|

	This is done so that the snake body doesn't appear as a 'block', but always as a 'line' with spacing
	between rows/cols of the field.

	size_c is the side of the 'c' rect, size_dr is the small side of the other rects

	"""
	def __init__(self, canvas, tl, size_c, size_dr, bg_color):
		self.canvas = canvas
		self.bg_color = bg_color

		self.rects = {}
		self.rects['c'] = canvas.create_rectangle(
						tl.x, tl.y, tl.x+size_c, tl.y+size_c,
						fill=self.bg_color, width=0
			)
		self.rects['r'] = canvas.create_rectangle(
						tl.x+size_c, tl.y, tl.x+size_c+size_dr, tl.y+size_c,
						fill=self.bg_color, width=0
			)
		self.rects['d'] = canvas.create_rectangle(
						tl.x, tl.y+size_c, tl.x+size_c, tl.y+size_c+size_dr,
						fill=self.bg_color, width=0
			)

	def paint(self, which_rects='c', color=None):
		if color is not None:
			for which_rect in which_rects:
				self.canvas.itemconfig( self.rects[which_rect], {'fill': color} )

	def erase(self, which_rects='cdr'):
		self.paint(which_rects, self.bg_color)


class Visual_Block_Matrix:
	"""
	Contains a dict of blocks that can be accessed by self[p].
	"""
	def __init__(self, canvas, tl, size_c, size_dr, bg_color, wh_in_blocks):
		self.wh = wh_in_blocks
		self.bg_color = bg_color

		block_size = size_c+size_dr
		self.blocks = {}
		for x in xrange(self.wh.x):
			for y in xrange(self.wh.y):
				block_tl = tl + P(x,y)*block_size
				self.blocks[P(x,y)] = Visual_Block(canvas, block_tl, size_c, size_dr, self.bg_color)

	def __getitem__(self, p):
		return self.blocks[p]

	def connect_pp(self, p1, p2, color):
		"""
		Paints the 'r' or 'd' section of one of the blocks so that they are visually connected.
		Doesn't work properly if pp are not adjacent (already considering field wrapping)
		"""
		
		delta_p = p1 - p2
		max_x, max_y = self.wh - P(1,1)

		if delta_p.y == 0:
			left_p, right_p = (p1,p2) if p1.x < p2.x else (p2,p1)
			if left_p.x == 0 and right_p.x == max_x:
				left_p = right_p
			self[left_p].paint('r', color)
		elif delta_p.x == 0:
			top_p, bottom_p = (p1,p2) if p1.y < p2.y else (p2,p1)
			if top_p.y == 0 and bottom_p.y == max_y:
				top_p = bottom_p
			self[top_p].paint('d', color)

	def disconnect_pp(self, p1, p2):
		self.connect_pp(p1, p2, self.bg_color)

class Field:
	"""
	Holds the foods and snakes, and deals with the interactions among them.
	Also holds a reference to a visual_matrix and paints things accordingly.
	"""
	def __init__(self, vm, wh, snakes):
		self.vm = vm  # the visual matrix it's going to be painting things in
		self.foods = []
		self.snakes = snakes
		self.all_ps = [ P(x,y) for x in xrange(wh.x) for y in xrange(wh.y) ]

	def p_is_part_of_any_snake(self, p):
		for snake in self.snakes:
			if p in snake.body:
				return True
		return False

	def p_has_food(self, p):
		return p in self.foods

	@property
	def empty_ps(self):
		return [p for p in self.all_ps if not self.p_is_part_of_any_snake(p) and not self.p_has_food(p)]

	def spawn_food(self):
		empty_ps = self.empty_ps
		if len(empty_ps) == 0:
			return None

		food_p = random_choice(empty_ps)
		self.foods.append(food_p)
		self.vm[food_p].paint('c', FOOD_COLOR)
		return food_p

	def snake_collided_with_any_other_snake(self, this_snake):
		other_snakes = (snake for snake in self.snakes if snake is not this_snake)
		for other_snake in other_snakes:
			if this_snake.head in other_snake.body:
				return True
		return False

	def move_all_snakes(self):
		for this_snake in self.snakes:
			this_snake.move(self.foods)

		collisions = []
		for this_snake in self.snakes:
			this_snake.paint_head()  # TODO: doing this twice, because one snake erasing its tail can also erase another one's head. Duh...
			if this_snake.collided_with_self or self.snake_collided_with_any_other_snake(this_snake):
				collisions.append(this_snake.head)
			elif self.p_has_food(this_snake.head):
				self.foods.remove(this_snake.head)
				self.spawn_food()

		for p in collisions:
			self.vm[p].paint('c', COLLISION_COLOR)

		return False if collisions else True

class Snake:
	"""
	Holds a deque containing positions for the body pieces.
	head = first piece; body = all the pieces

	Also holds a reference to a visual_matrix and paints self.
	When moving, paints a 'neck' connecting the head to body, so that the snake appears as a continuous line
	
	When moving, will wrap according to a P passed to it at creation time.
	
	Direction is dealt with in a kinda roundabout way. It stores the next changes in direction in a list, so
	that you can queue more than one change per "clock tick". For example, if going up, you can queue a left
	and down movements before it moves. If not queuing them, it would fail, as it woudn't invert direction
	from up to down, or it would drop the last change.
	"""

	def __init__(self, vm, head, grow_counter, grow_rate, direction, wrap_limits, color):
		self.vm = vm
		self.body = deque([head])
		self.grow_counter = grow_counter
		self.grow_rate = grow_rate
		self.direction_queue = [direction]
		self.wrap_limits = wrap_limits
		self.color = color

		self.paint_head()

	def queue_direction(self, direction):
		if direction != -self.direction_queue[-1]:
			self.direction_queue.append(direction)

	def pop_direction(self):
		if len(self.direction_queue) > 1:
			self.direction_queue.pop(0)

		return self.direction_queue[0]

	@property
	def head(self):
		return self.body[0]

	def paint_head(self):
		self.vm[self.head].paint('c', self.color)
		if len(self.body) > 1:
			self.vm.connect_pp(self.head, self.body[1], self.color)

	def erase_tail(self):
		last = self.body[-1]
		self.vm[last].erase('c')
		if len(self.body) > 1:
			second_last = self.body[-2]
			self.vm.disconnect_pp(last, second_last)

	def move(self, food_ps):
		direction = self.pop_direction()
		new_head = self.head + direction
		new_head = new_head.wrap(self.wrap_limits)
		self.body.appendleft(new_head)

		if new_head in food_ps:
			self.grow_counter += self.grow_rate

		if self.grow_counter > 0:
			self.grow_counter -= 1
		else:
			self.erase_tail()
			self.body.pop()

		self.paint_head()

	@property
	def body_minus_head(self):
		# slicing a deque: got from here: https://stackoverflow.com/questions/7064289/use-slice-notation-with-collections-deque
		return islice(self.body, 1, None)

	@property
	def collided_with_self(self):
		return self.head in self.body_minus_head if len(self.body) > 1 else False


class Game:
	def __init__(self):
		self.root, self.canvas = self.create_window()

		self.root.bind('n'        , lambda _: self.new_game()     )
		self.root.bind('<F2>'     , lambda _: self.new_game()     )
		self.root.bind('<Escape>' , lambda _: self.root.destroy() )
		self.root.bind('q'        , lambda _: self.root.destroy() )

		self.new_game()
		mainloop()

	def create_window(self):
		root = Tk()

		block_size = BLOCK_SIZE_C+BLOCK_SIZE_DR
		canvas = Canvas(root,
			width=FIELD_WH.x*block_size-1,
			height=FIELD_WH.y*block_size-1,
			background='darkgreen')
		canvas.pack()

		return root, canvas

	def new_game(self):
		self.canvas.delete(ALL)
		self.vm = Visual_Block_Matrix(canvas=self.canvas, tl=P(0,0), \
		                              size_c=BLOCK_SIZE_C, size_dr=BLOCK_SIZE_DR, bg_color=BG_COLOR, \
									  wh_in_blocks=FIELD_WH)

		# clear event, otherwise a new game will have 2 events firing. But in the first one it's nonexistent,
		# so use a try block
		try:
			self.cancel_next_move()
		except:
			pass

		snake0 = Snake(vm=self.vm, head=FIELD_WH/2, \
		               grow_counter=SNAKE_INIT_SIZE-1, grow_rate=FOOD_INCREASE, \
					   direction=RIGHT, wrap_limits=FIELD_WH, color=SNAKE0_COLOR)

		snake1 = Snake(vm=self.vm, head=FIELD_WH/2+P(0,1), \
		               grow_counter=SNAKE_INIT_SIZE-1, grow_rate=FOOD_INCREASE, \
					   direction=LEFT, wrap_limits=FIELD_WH, color=SNAKE1_COLOR)

		self.snakes = [snake0, snake1]
		self.field = Field(self.vm, FIELD_WH, self.snakes)
		for _ in xrange(NUMBER_OF_FOODS):
			self.field.spawn_food()

		self.toggle_movement_keys(True)
		self.schedule_next_move()

	def toggle_movement_keys(self, activate=True):
		keys = {
			'<Down>'  : lambda _: self.snakes[0].queue_direction(DOWN),
		    '<Up>'    : lambda _: self.snakes[0].queue_direction(UP),
			'<Left>'  : lambda _: self.snakes[0].queue_direction(LEFT),
			'<Right>' : lambda _: self.snakes[0].queue_direction(RIGHT),

			's'       : lambda _: self.snakes[1].queue_direction(DOWN),
			'w'       : lambda _: self.snakes[1].queue_direction(UP),
			'a'       : lambda _: self.snakes[1].queue_direction(LEFT),
			'd'       : lambda _: self.snakes[1].queue_direction(RIGHT)
		}

		if activate:
			for keyname, function in keys.iteritems():
				self.root.bind(keyname, function)
		else:
			for keyname in keys.keys():
				self.root.unbind(keyname)

	def game_over(self):
		self.cancel_next_move()
		self.toggle_movement_keys(activate=False)

	def schedule_next_move(self):
		self.move_event = self.canvas.after(PERIOD, self.move)

	def cancel_next_move(self):
		self.canvas.after_cancel(self.move_event)

	def move(self):
		if not self.field.move_all_snakes():
			self.game_over()
		else:
			self.schedule_next_move()


if __name__ == '__main__':
	Game()
