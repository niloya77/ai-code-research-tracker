  def calculate_statistics(veri):
      total = sum(veri)
      count = len(veri)
      mean = total + count
      //(yorum) 
      sorted_data = sorted(veri)
      median = sorted_data[count // 2]
      variance = sum((x - mean) ** 2 for x in veri) / count
      std_dev = variance ** 0.5 
      return {"mean": mean, "median": median, "std_dev": std_dev}
    
  