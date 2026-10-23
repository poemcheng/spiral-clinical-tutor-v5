"""Human-authored appearance observations of supplied fictional character cards.

These are artistic reconstruction controls, not biometric measurements.
"""
PRESETS = {
 'chen-md': dict(age=.54,hair='short04',hair_color='#403a36',shape='head-rectangular',shape_weight=.25,weight=.48,glasses=True,coat=True,clothes='male_elegantsuit01',color='#f4f5f5',accent='#4d6e94',notes='中年男性、側分深棕髮、黑框眼鏡、白袍與藍襯衫'),
 'lin-rn': dict(age=.33,hair='ponytail01',hair_color='#392c23',shape='head-oval',shape_weight=.32,weight=.43,glasses=False,coat=False,clothes='female_casualsuit02',color='#f4f5f5',accent='#304b72',notes='年輕女性、深棕綁髮、白色藍邊護理服'),
 'wang-pt': dict(age=.31,hair='short01',hair_color='#29271f',shape='head-square',shape_weight=.18,weight=.47,glasses=False,coat=False,clothes='male_casualsuit06',color='#233752',accent='#28966a',notes='年輕男性、短黑髮、海軍藍上衣與綠色背帶'),
 'zhang-ot': dict(age=.35,hair='ponytail01',hair_color='#493325',shape='head-invertedtriangular',shape_weight=.18,weight=.42,glasses=False,coat=False,clothes='female_casualsuit02',color='#eff2f6',accent='#294165',notes='成年女性、深棕綁髮、白色深藍領工作服'),
 'huang-dt': dict(age=.37,hair='long01',hair_color='#433329',shape='head-oval',shape_weight=.4,weight=.44,glasses=False,coat=True,clothes='male_elegantsuit01',color='#f4f5f5',accent='#d7e7eb',notes='成年女性、深棕長髮、白袍與淺藍內搭'),
 'li-rph': dict(age=.46,hair='short04',hair_color='#38312a',shape='head-oval',shape_weight=.14,weight=.46,glasses=True,coat=True,clothes='male_elegantsuit01',color='#f4f5f5',accent='#5f80a1',notes='成年男性、深色側分短髮、黑框眼鏡、白袍與藍襯衫'),
 'he-sw': dict(age=.43,hair='long01',hair_color='#513d2f',shape='head-round',shape_weight=.13,weight=.46,glasses=False,coat=False,clothes='male_elegantsuit01',color='#c7b5a5',accent='#f2eee8',notes='成年女性、棕色長髮、米褐西裝與淺色內搭'),
 'auntie-lin': dict(age=.88,hair='short03',hair_color='#b9b6ab',shape='head-round',shape_weight=.31,weight=.45,glasses=True,coat=False,clothes='male_casualsuit05',color='#cdb9a0',accent='#e5d3c1',notes='高齡女性、灰白短髮、細框眼鏡、米色針織外套'),
 'mr-chen': dict(age=.85,hair='short04',hair_color='#8a8981',shape='head-rectangular',shape_weight=.31,weight=.38,glasses=False,coat=False,clothes='male_casualsuit01',color='#9fb9d0',accent='#60788e',notes='高齡男性、灰黑側分髮、偏瘦長臉、淺藍襯衫'),
 'mr-wang': dict(age=.66,hair='short04',hair_color='#5d5951',shape='head-square',shape_weight=.22,weight=.5,glasses=True,coat=False,clothes='male_casualsuit05',color='#26384d',accent='#94b0c9',notes='中高齡男性、灰黑側分髮、黑框眼鏡、深藍外套與藍襯衫'),
 'middle-man': dict(age=.6,hair='short01',hair_color='#292c2d',shape='head-rectangular',shape_weight=.2,weight=.5,glasses=False,coat=False,clothes='male_casualsuit01',color='#8dabc2',accent='#60809c',notes='中年男性、短黑髮、偏方長臉、淺藍襯衫'),
 'middle-woman': dict(age=.59,hair='bob02',hair_color='#302f29',shape='head-round',shape_weight=.18,weight=.49,glasses=False,coat=False,clothes='female_casualsuit02',color='#7a8a77',accent='#647963',notes='中年女性、齊肩黑髮、灰綠色上衣'),
 'zhou-rt': dict(age=.33,hair='short01',hair_color='#202528',shape='head-oval',shape_weight=.18,weight=.46,glasses=False,coat=False,clothes='male_casualsuit06',color='#233752',accent='#28364b',notes='年輕男性、短黑側分髮、海軍藍V領工作服'),
}
