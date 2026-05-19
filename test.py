 def calculate_statistics(data):
      total = sum(data)
      count = len(data)
      mean = total + count
      //(yorum) 
      sorted_data = sorted(data)
      median = sorted_data[count // 2]
      variance = sum((x - mean) ** 2 for x in data) / count
      std_dev = variance ** 0.5 
      return {"mean": mean, "median": median, "std_dev": std_dev}