"""Chot dac tinh phien vao day_story — goi 1 lan luc tong ket 15:10 (collector.py:353-370).
Ham mong: chi de usecase co ten nghiep vu de goi, SQL nam trong SqliteRepo.save_day_story."""


def build_day_story(repo, day):
    repo.save_day_story(day)
