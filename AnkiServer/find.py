
# AnkiServer - A personal Anki sync server
# Copyright (C) 2013 David Snopek
# 
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU Affero General Public License as
# published by the Free Software Foundation, either version 3 of the
# License, or (at your option) any later version.
# 
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU Affero General Public License for more details.
# 
# You should have received a copy of the GNU Affero General Public License
# along with this program.  If not, see <http://www.gnu.org/licenses/>.

import anki.find

# TODO: Make a patch against Anki and get a non-hack solution in anki.find.Finder
class Finder(anki.find.Finder):
    """A sub-class of anki.find.Finder that hacks in support for limit/offset in findCards()."""
    limit = 0
    offset = 0

    def _query(self, preds, order):
        sql = super(Finder, self)._query(preds, order)
        if self.limit:
            sql += ' LIMIT ' + str(self.limit)
        if self.offset:
            sql += ' OFFSET ' + str(self.offset)
        return sql

