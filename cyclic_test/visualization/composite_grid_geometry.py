class CompositeGridGeometry:
    def __init__(self, cell_size, transition_scale=2 / 3):
        self.cell_size = cell_size
        self.transition_scale = transition_scale
        self.transition_size = max(1, int(round(cell_size * transition_scale)))

    def get_total_size(self, composite_map):
        height = len(composite_map)
        width = len(composite_map[0]) if height > 0 else 0
        return (self.get_total_width(width), self.get_total_height(height))

    def get_total_width(self, num_columns):
        return self._get_total_extent(num_columns)

    def get_total_height(self, num_rows):
        return self._get_total_extent(num_rows)

    def get_cell_bounds(self, row_index, column_index):
        left = self._get_axis_offset(column_index)
        top = self._get_axis_offset(row_index)
        right = left + self._get_axis_size(column_index) - 1
        bottom = top + self._get_axis_size(row_index) - 1
        return (left, top, right, bottom)

    def _get_total_extent(self, num_indices):
        return sum(self._get_axis_size(index) for index in range(num_indices))

    def _get_axis_offset(self, index):
        return sum(self._get_axis_size(current_index) for current_index in range(index))

    def _get_axis_size(self, index):
        if index % 2 == 0:
            return self.cell_size
        return self.transition_size
